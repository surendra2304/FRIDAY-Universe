"""
Regression tests for two silent-data-loss bugs in the deterministic Script
generator (`_script_main` in app/agents/synthesis.py), found by actually
generating a script and running it against real files on disk -- not by
reading the source or trusting the generated project's own test suite
(which asserted on the *happy path* only and could not have caught either
bug, since both only manifest with inputs the original tests never tried).

Finding 18 -- `rename_lower` silently destroyed a file on a case collision:
    Two differently-cased files in one directory (e.g. README.MD and
    readme.md) both normalize to the same lowercase target. The generated
    code called `path.rename(target)` unconditionally, and `Path.rename()`
    silently overwrites an existing destination on POSIX. Live repro: a
    directory with A.txt, README.MD, and readme.md went from 3 files to 2
    after `rename --apply` -- readme.md's original content was gone, with
    no error and an exit code of 0. The CLI's own success message also said
    "file(s) would be renamed" even when `--apply` was passed and files were
    actually renamed, which would have made the data loss even harder to
    notice.

Finding 20 -- `json_to_csv` corrupted its output on inconsistent rows and
crashed with a raw traceback on non-dict array items:
    `fieldnames` was taken only from the first row's keys, so a later row
    with an extra key (a very common shape for loosely-structured JSON
    exports) made `csv.DictWriter.writerows` raise partway through --
    *after* the header and every prior row had already been written
    straight to the target file, leaving a truncated, silently corrupted
    CSV on disk despite the command reporting an error and a non-zero exit
    code. Separately, a non-dict item in the JSON array (e.g. a bare
    string) raised an unhandled `AttributeError: 'str' object has no
    attribute 'keys'` with a raw internal traceback instead of a clean,
    actionable error message.

Finding 19 -- `backup_today` silently lost a file to a flattening collision:
    `source.rglob("*")` walks subdirectories, but every match was copied to
    `target / path.name` -- a flat basename-only destination. Two files with
    the same name in different subdirectories (e.g. sub1/data.txt and
    sub2/data.txt) collided on the same flat destination, and the second
    `shutil.copy2()` silently overwrote the first. Live repro: backing up a
    tree containing both files reported "copied 2 file(s)" (i.e. claimed
    full success) while the backup folder only ever contained one data.txt,
    with the other file's content permanently gone from the backup.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest

from app.agents.synthesis import synthesize_project


def _load_generated_script(tmp_path: Path, goal: str):
    files = synthesize_project(goal)
    main_name = next(name for name in files if name.endswith(".py") and not name.startswith("test_"))
    tmp_path.mkdir(parents=True, exist_ok=True)
    script_path = tmp_path / "generated_script.py"
    script_path.write_text(files[main_name])

    mod_name = f"forge_generated_script_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(mod_name, script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


GOAL = "Write a script that renames all files in a directory to lowercase"


@pytest.fixture
def generated_script(tmp_path):
    return _load_generated_script(tmp_path / "module_src", GOAL)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Filesystem is case-insensitive on Windows; two files differing only in case cannot coexist in the same directory",
)
def test_rename_lower_never_silently_destroys_a_colliding_file(tmp_path, generated_script):
    work = tmp_path / "files"
    work.mkdir()
    (work / "A.txt").write_text("content-A")
    (work / "README.MD").write_text("content-upper-readme")
    (work / "readme.md").write_text("content-lower-readme")

    plan = generated_script.rename_lower(work, apply=True)

    # A.txt -> a.txt should still have happened (no collision).
    assert (work / "a.txt").exists()
    assert (work / "a.txt").read_text() == "content-A"

    # The actual regression: both differently-cased readme files must still
    # exist with their original, distinct content. Before the fix, one of
    # them was silently overwritten by Path.rename().
    assert (work / "README.MD").exists(), "README.MD was destroyed by the colliding rename"
    assert (work / "readme.md").exists()
    assert (work / "README.MD").read_text() == "content-upper-readme"
    assert (work / "readme.md").read_text() == "content-lower-readme"

    # The collision must not be reported as a completed rename.
    renamed_sources = {src.name for src, _dst in plan}
    assert "README.MD" not in renamed_sources


def test_backup_today_does_not_flatten_colliding_basenames(tmp_path, generated_script):
    source = tmp_path / "source"
    (source / "sub1").mkdir(parents=True)
    (source / "sub2").mkdir(parents=True)
    (source / "sub1" / "data.txt").write_text("from-sub1")
    (source / "sub2" / "data.txt").write_text("from-sub2")

    target = tmp_path / "backup_out"
    copied = generated_script.backup_today(source, target)

    assert len(copied) == 2, f"expected both files to be backed up, got {copied}"

    # The actual regression: both files must survive with distinct content,
    # not collapse onto a single flattened target/data.txt.
    all_backed_up_content = {p.read_text() for p in target.rglob("*") if p.is_file()}
    assert all_backed_up_content == {"from-sub1", "from-sub2"}, (
        f"backup lost data to a flattening collision: {all_backed_up_content}"
    )


def test_json_to_csv_handles_rows_with_inconsistent_keys(tmp_path, generated_script):
    source = tmp_path / "rows.json"
    source.write_text(
        '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25, "city": "NYC"}]'
    )
    target = tmp_path / "out.csv"

    count = generated_script.json_to_csv(source, target)

    assert count == 2
    text = target.read_text()
    # The header must be the union of every row's keys, in first-seen order,
    # and the file must contain BOTH rows in full -- not a truncated file
    # that stops after the first row once DictWriter hit the mismatch.
    lines = [line for line in text.splitlines() if line]
    assert lines[0] == "name,age,city"
    assert len(lines) == 3, f"expected header + 2 full rows, got: {lines!r}"
    assert "Bob" in text and "NYC" in text


def test_json_to_csv_rejects_non_dict_rows_with_a_clean_error(tmp_path, generated_script):
    source = tmp_path / "rows.json"
    source.write_text('["just", "a", "list", "of", "strings"]')
    target = tmp_path / "out.csv"

    with pytest.raises(ValueError, match="row 0 is not a JSON object"):
        generated_script.json_to_csv(source, target)


def test_rename_cli_message_reflects_whether_apply_was_used(tmp_path, capsys):
    script = _load_generated_script(tmp_path / "module_src_cli", GOAL)
    work = tmp_path / "files"
    work.mkdir()
    (work / "UPPER.TXT").write_text("x")

    exit_code = script.main(["rename", str(work), "--apply"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "renamed" in out
    assert "would be renamed" not in out, (
        "CLI said 'would be renamed' even though --apply actually renamed files"
    )
