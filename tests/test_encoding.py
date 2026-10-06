"""Files that tools parse must be ASCII-only.

This exists because of a real five-day outage. `.gitignore` carried an em dash
in a comment I wrote. GitHub runners set no UTF-8 locale, so Python's `open()`
falls back to ASCII, and DVC died reading it:

    ERROR: unexpected error - 'ascii' codec can't encode character '\\u2014'
           in position 171: ordinal not in range(128)

Every scheduled archive run failed. The weather vintage was collected correctly
each time and then discarded, because the failing step meant `dvc push` never
ran. Five days of vintages are unrecoverable.

It never reproduced locally: macOS sets a UTF-8 locale, so the same code read
the same file without complaint. That is the shape of the bug worth guarding -
it is invisible on the machine you develop on.

Prose documents are deliberately exempt. Nothing parses them with a locale
codec; they are read by people and by GitHub's markdown renderer.
"""

from __future__ import annotations

import pytest

from src.config import PROJECT_ROOT

# Parsed by pip, make, docker, DVC, PyYAML, ruff or GitHub Actions - all of
# which may open them with the ambient locale encoding.
TOOL_PARSED = [
    ".gitignore",
    ".dvcignore",
    ".dockerignore",
    "config/config.yaml",
    "requirements.txt",
    "ruff.toml",
    "pytest.ini",
    "Makefile",
    "Dockerfile",
    "data/external/festivals_in.csv",
    ".github/workflows/ci.yml",
    ".github/workflows/archive.yml",
]


@pytest.mark.parametrize("relpath", TOOL_PARSED)
def test_tool_parsed_files_are_ascii(relpath):
    path = PROJECT_ROOT / relpath
    if not path.exists():
        pytest.skip(f"{relpath} absent")
    raw = path.read_bytes()
    try:
        raw.decode("ascii")
    except UnicodeDecodeError:
        text = raw.decode("utf-8")
        offenders = sorted({c for c in text if ord(c) > 127})
        lines = [i for i, line in enumerate(text.splitlines(), 1)
                 if any(ord(c) > 127 for c in line)]
        pytest.fail(
            f"{relpath} contains non-ASCII {offenders} on line(s) {lines}. "
            "A tool reads this file with the ambient locale encoding, which is "
            "ASCII on a GitHub runner. Use plain hyphens and quotes here; "
            "typography belongs in the .md documents."
        )


def test_project_python_pins_its_file_encoding():
    """`open()` without `encoding=` uses the ambient locale, so the same code
    reads a file on macOS and crashes on a runner.

    Walks the AST rather than the text: a first attempt scanned lines and
    flagged its own docstring, which is the sort of false positive that gets a
    test deleted rather than fixed.
    """
    import ast

    watched = {"open", "read_text", "write_text"}
    exempt = {"safe_dump", "urlopen"}
    offenders = []
    for folder in ("src", "scripts", "tests"):
        for path in sorted((PROJECT_ROOT / folder).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = (fn.attr if isinstance(fn, ast.Attribute)
                        else fn.id if isinstance(fn, ast.Name) else None)
                if name not in watched:
                    continue
                if any(isinstance(a, ast.Call)
                       and getattr(a.func, "attr", getattr(a.func, "id", None))
                       in exempt for a in node.args):
                    continue
                # A binary-mode open needs no encoding.
                modes = [a.value for a in node.args
                         if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                if any("b" in m for m in modes):
                    continue
                if not any(k.arg == "encoding" for k in node.keywords):
                    offenders.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} {name}()")
    assert not offenders, (
        "file IO without an explicit encoding, which uses the ambient locale "
        "and therefore behaves differently on a runner: " + ", ".join(offenders))


def test_the_workflows_force_utf8_mode():
    """Belt and braces: even with every file ASCII today, a future edit should
    not be able to break the runner."""
    import yaml
    for name in ("archive.yml", "ci.yml"):
        path = PROJECT_ROOT / ".github" / "workflows" / name
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        env = spec.get("env") or {}
        assert str(env.get("PYTHONUTF8")) == "1", f"{name} must set PYTHONUTF8=1"
