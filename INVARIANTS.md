# INVARIANTS.md

Constraints on the shape of `rcy-export` that hold for every generation,
whatever features SPEC.md adds. A generator reads this file with SPEC.md.

**I5. Generated code is disposable.** The program under `build/` is a build
output. A defect is fixed by editing SPEC.md or adding a scenario and
generating again, never by editing the artifact.

**I6. One file, no dependencies beyond the SDK.** The artifact is a single
executable JavaScript file named `rcy-export`, run by Node.js, so its hash
identifies the whole program. It is the output of
`node rcy-sdk/dist/bundle.cjs output/main.js output/rcy-export`: the bytes of
`rcy-sdk/dist/rcy-sdk.js`, unchanged, followed by the generated program. The
generated program loads only Node's built-in modules and uses the SDK through
the constant `rcySdk`. It requires Node.js 22 or later and behaves identically
on every later version. Types are written as JSDoc annotations. On an older
runtime it exits with code 1 and one stderr line naming the required version.

**I11. File formats belong to the SDK.** The program writes no byte of a WAV,
MIDI, SFZ, manifest or EXS file except through the `rcySdk` function SPEC.md
names for it, and parses WAV only through `rcySdk.parseWav`. It reads a
manifest with `JSON.parse`; a text `JSON.parse` rejects is the
`<path>: invalid JSON` refusal.

**I7. No fallbacks on required input.** A missing option, variable or file
that SPEC.md gives a message for is a named refusal. The program never substitutes a default path, a built-in
catalog or a nearby file for one the user had to supply.

**I8. Audio passes through untouched.** Slice frames are copied from the
source as bytes. No generation resamples, requantises, normalises, fades or
dithers unless SPEC.md states the exact arithmetic.

**I9. Integer positions.** Frame positions are computed in integer arithmetic
wherever SPEC.md gives an integer formula, and in exact rational arithmetic
where it says so. Floating point is used only where SPEC.md calls for a
double.

**I10. Deterministic output.** The same arguments, environment, working directory
and input files produce byte-identical output files. Nothing written depends on the clock,
the locale, the user name or a random source.
