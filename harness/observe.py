"""Read files a candidate wrote and turn them into trace events.

Every reader here is standard library code the candidate did not write: `wave`
for WAV headers and frames, `json` for JSON, and readers for Standard MIDI
Files and EXS instruments below. The events carry file-format facts only (a channel count, a line of
text, a tick); nothing here knows what the candidate is for.
"""
import hashlib
import json
import struct
import wave
from pathlib import Path

from riemann_harness.trace import flatten

TEXT_SUFFIXES = {".sfz", ".txt"}


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        facts = {"channels": w.getnchannels(), "rate": w.getframerate(),
                 "width": w.getsampwidth() * 8, "frames": w.getnframes()}
        return facts, w.readframes(w.getnframes())


def _varlen(data, pos):
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos


def read_midi(data):
    """Return (header, events). Each event has track, tick and kind."""
    if data[:4] != b"MThd" or struct.unpack(">I", data[4:8])[0] != 6:
        raise ValueError("not a Standard MIDI File")
    fmt, tracks, division = struct.unpack(">HHH", data[8:14])
    header = {"format": fmt, "tracks": tracks, "division": division}
    events, pos = [], 14
    for track in range(tracks):
        if data[pos:pos + 4] != b"MTrk":
            raise ValueError("missing track chunk")
        end = pos + 8 + struct.unpack(">I", data[pos + 4:pos + 8])[0]
        pos += 8
        if end > len(data):
            raise ValueError("track chunk runs past the end of the file")
        tick, status = 0, None
        while pos < end:
            delta, pos = _varlen(data, pos)
            tick += delta
            if data[pos] & 0x80:
                status = data[pos]
                pos += 1
            if status == 0xFF:
                kind = data[pos]
                length, pos = _varlen(data, pos + 1)
                body = data[pos:pos + length]
                pos += length
                if kind == 0x51:
                    events.append({"track": track, "tick": tick, "kind": "tempo",
                                   "microseconds": int.from_bytes(body, "big")})
                elif kind == 0x58:
                    events.append({"track": track, "tick": tick, "kind": "time_signature",
                                   "numerator": body[0], "denominator": 2 ** body[1]})
                elif kind == 0x2F:
                    events.append({"track": track, "tick": tick, "kind": "end_of_track"})
            elif status in (0xF0, 0xF7):
                length, pos = _varlen(data, pos)
                pos += length
            else:
                high, channel = status & 0xF0, status & 0x0F
                size = 1 if high in (0xC0, 0xD0) else 2
                a = data[pos]
                b = data[pos + 1] if size == 2 else 0
                pos += size
                # A note-on with velocity 0 is a note-off by the MIDI standard.
                if high == 0x90 and b > 0:
                    events.append({"track": track, "tick": tick, "kind": "note_on",
                                   "channel": channel, "key": a, "velocity": b})
                elif high in (0x80, 0x90):
                    events.append({"track": track, "tick": tick, "kind": "note_off",
                                   "channel": channel, "key": a})
        pos = end
    return header, events


EXS_HEADER = 84  # bytes before each block's content
EXS_TYPES = {0: "instrument", 1: "zone", 2: "group", 3: "sample", 4: "params"}


def read_exs(data):
    """Return the blocks of a little-endian EXS instrument as (type, name, content)."""
    blocks, pos = [], 0
    while pos < len(data):
        if pos + EXS_HEADER > len(data) or data[pos:pos + 3] != b"\x01\x01\x00" or data[pos + 16:pos + 20] != b"TBOS":
            raise ValueError(f"no little-endian EXS block header at byte {pos}")
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        end = pos + EXS_HEADER + size
        if end > len(data):
            raise ValueError("EXS block runs past the end of the file")
        name = data[pos + 20:pos + 84].split(b"\0")[0].decode("ascii")
        blocks.append((EXS_TYPES[data[pos + 3]], name, data[pos + EXS_HEADER:end]))
        pos = end
    return blocks


def wav_data_chunk(path):
    """Return (offset of the first frame, length of the file) by walking RIFF chunks."""
    raw = Path(path).read_bytes()
    pos = 12
    while pos + 8 <= len(raw):
        length = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        if raw[pos:pos + 4] == b"data":
            return pos + 8, len(raw)
        pos += 8 + length + (length & 1)
    raise ValueError("no data chunk")


def observe_exs(trace, root, name, path):
    """Record an EXS instrument's counts, zones and sample references. Each
    sample event says whether the file it names exists in the stored folder
    and whether the stored facts agree with that file."""
    blocks = read_exs(path.read_bytes())
    kinds = [kind for kind, _, _ in blocks]
    head = struct.unpack("<5I", blocks[0][2][:20])
    data = path.read_bytes()
    words, pos = {}, 0
    for kind in kinds:  # the flag word in each block header, per block type
        words.setdefault(kind, set()).add(struct.unpack("<I", data[pos + 12:pos + 16])[0])
        pos += EXS_HEADER + struct.unpack("<I", data[pos + 4:pos + 8])[0]
    digest = lambda kind: hashlib.sha256(b"".join(c for k, _, c in blocks if k == kind)).hexdigest()
    trace.record("exs_layout", file=name, header_flags={k: sorted(v) for k, v in words.items()},
                 sizes={k: sorted({len(c) for kk, _, c in blocks if kk == k}) for k in words},
                 group_sha256=digest("group"), params_sha256=digest("params"),
                 zone_word_84=sorted({struct.unpack("<I", c[84:88])[0] for k, _, c in blocks if k == "zone"}))
    trace.record("exs", file=name, name=blocks[0][1], order=sorted(set(kinds), key=kinds.index),
                 zones=kinds.count("zone"), groups=kinds.count("group"), samples=kinds.count("sample"),
                 params=kinds.count("params"), declared_zones=head[1], declared_groups=head[2],
                 declared_samples=head[3])
    for index, content in enumerate(c for kind, _, c in blocks if kind == "zone"):
        start, end, _, loop_end = struct.unpack("<4I", content[12:28])
        trace.record("exs_zone", file=name, index=index, one_shot=bool(content[0] & 1),
                     reverse=bool(content[0] & 4), root=content[1], tune=content[2], pan=content[3],
                     volume=content[4], key_low=content[6], key_high=content[7],
                     velocity_low=content[9], velocity_high=content[10], start=start, end=end,
                     loop_on=bool(content[33] & 1), loop_end=loop_end,
                     group=struct.unpack("<i", content[88:92])[0], sample=struct.unpack("<I", content[92:96])[0])
    for index, (block_name, content) in enumerate((n, c) for kind, n, c in blocks if kind == "sample"):
        offset, frames, rate, width, channels = struct.unpack("<5I", content[0:20])
        folder = content[80:336].split(b"\0")[0].decode("ascii")
        file_name = content[336:592].split(b"\0")[0].decode("ascii")
        target = Path(folder) / file_name
        matches = False
        if target.is_file():
            facts, _ = read_wav(target)
            matches = ((offset, struct.unpack("<I", content[32:36])[0]) == wav_data_chunk(target)
                       and facts == {"channels": channels, "rate": rate, "width": width, "frames": frames})
        trace.record("exs_sample", file=name, index=index, block_name=block_name, name=file_name,
                     folder=folder.replace(str(root), "$WORK"), type=content[28:32].decode("ascii"),
                     frames=frames, rate=rate, width=width, channels=channels,
                     exists=target.is_file(), matches_wav=matches)


def observe(trace, root, directory):
    """Record one `file` event per file under `directory`, plus format events."""
    base = (root / directory).resolve()
    if not base.is_dir():
        trace.record("directory_absent", dir=directory)
        return
    files = sorted(p for p in base.rglob("*") if p.is_file())
    dirs = sum(1 for p in base.rglob("*") if p.is_dir())
    trace.record("directory", dir=directory, files=len(files), dirs=dirs)
    for path in files:
        name = path.relative_to(root).as_posix()
        trace.record("file", file=name, dir=directory)
        try:
            suffix = path.suffix.lower()
            if suffix == ".wav":
                facts, _ = read_wav(path)
                trace.record("wav", file=name, **facts)
            elif suffix == ".json":
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
                # indent2: the text is the two-space indented form plus one newline.
                trace.record("json", file=name, indent2=raw == json.dumps(data, indent=2) + "\n",
                             keys=list(data) if isinstance(data, dict) else None, **flatten(data))
                for index, text in enumerate(raw.split("\n"), start=1):
                    trace.record("text_line", file=name, index=index, text=text)
            elif suffix in TEXT_SUFFIXES:
                raw = path.read_text(encoding="utf-8")
                lines = raw.split("\n")
                trace.record("text", file=name, lines=len(lines), final_newline=raw.endswith("\n"))
                for index, text in enumerate(lines, start=1):
                    trace.record("text_line", file=name, index=index, text=text)
            elif suffix == ".exs":
                observe_exs(trace, root, name, path)
            elif suffix == ".mid":
                header, events = read_midi(path.read_bytes())
                trace.record("midi", file=name, **header)
                for event in events:
                    trace.record("midi_event", file=name, **event)
        except Exception as exc:  # an unreadable output is evidence, not a harness crash
            trace.record("unreadable", file=name, error=type(exc).__name__ + ": " + str(exc))


def compare(trace, root, file, source, start, end):
    """Record whether `file` holds exactly frames [start, end) of `source`."""
    try:
        got_facts, got = read_wav(root / file)
        src_facts, src = read_wav(root / source)
        size = src_facts["channels"] * src_facts["width"] // 8
        same_format = all(got_facts[k] == src_facts[k] for k in ("channels", "rate", "width"))
        equal = same_format and got == src[start * size:end * size] and len(got) == (end - start) * size
        trace.record("frames_compared", file=file, source=source, start=start, end=end, equal=bool(equal))
    except Exception as exc:
        trace.record("frames_compared", file=file, source=source, start=start, end=end,
                     equal=False, error=type(exc).__name__ + ": " + str(exc))


def identical(trace, root, first, second):
    """Record whether two files hold the same bytes."""
    try:
        equal = (root / first).read_bytes() == (root / second).read_bytes()
        trace.record("files_compared", first=first, second=second, equal=equal)
    except OSError as exc:
        trace.record("files_compared", first=first, second=second, equal=False,
                     error=type(exc).__name__ + ": " + str(exc))
