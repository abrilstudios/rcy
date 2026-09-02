"""Tests for the rcy-push plugin dispatcher."""

import os
import stat

import pytest

from push_dispatch import PLUGIN_REPOS, main


@pytest.fixture
def empty_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))
    return bin_dir


def test_missing_plugin_exits_2_and_names_executable(empty_path, capsys):
    code = main(["nothing", "--manifest", "x.json"])

    err = capsys.readouterr().err
    assert code == 2
    assert "rcy-push-nothing" in err
    for repo in PLUGIN_REPOS:
        assert repo in err


def test_plugin_receives_args_and_output_is_relayed(empty_path, capfd):
    script = empty_path / "rcy-push-fake"
    script.write_text('#!/bin/sh\necho "args: $@"\nexit 7\n')
    script.chmod(script.stat().st_mode | stat.S_IXUSR)

    code = main(["fake", "--manifest", "kit.rcy.json", "--bank", "A", "--dry-run"])

    out = capfd.readouterr().out
    assert code == 7
    assert out == "args: --manifest kit.rcy.json --bank A --dry-run\n"


def test_missing_manifest_is_a_usage_error(empty_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["fake"])
    assert exc.value.code == 2
    assert "--manifest" in capsys.readouterr().err


def test_which_ignores_non_executable_file(empty_path, capsys):
    script = empty_path / "rcy-push-fake"
    script.write_text("#!/bin/sh\n")
    script.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert not os.access(script, os.X_OK)

    assert main(["fake", "--manifest", "kit.rcy.json"]) == 2
    assert "rcy-push-fake" in capsys.readouterr().err
