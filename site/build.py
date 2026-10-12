"""Build the use-cases page from site/template.html and the scripts in examples/.

Every "works today" block on the page is the exact source of an example script, and
every output block is what that script printed when this ran. Run it from the repo
root with network access:

    uv run --with pandas python site/build.py

It writes site/public/index.html, which is committed; deploying needs no build step.
"""

from __future__ import annotations

import datetime as dt
import html
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
TEMPLATE = ROOT / "site" / "template.html"
OUTPUT = ROOT / "site" / "public" / "index.html"

PLACEHOLDER = re.compile(r"<!--(example|output|name):(\d\d)-->")


def highlight(source: str) -> str:
    """Escape Python source for HTML, wrapping comments and docstrings in spans."""
    spans: list[tuple[tuple[int, int], tuple[int, int], str]] = []
    previous = tokenize.NEWLINE
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            spans.append((token.start, token.end, "c"))
        elif token.type == tokenize.STRING and previous in (tokenize.NEWLINE, tokenize.NL):
            spans.append((token.start, token.end, "c"))  # a docstring statement
        if token.type not in (tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
            previous = token.type

    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def absolute(position: tuple[int, int]) -> int:
        return offsets[position[0] - 1] + position[1]

    out, cursor = [], 0
    for start, end, css in spans:
        a, b = absolute(start), absolute(end)
        out.append(html.escape(source[cursor:a]))
        out.append(f'<span class="{css}">{html.escape(source[a:b])}</span>')
        cursor = b
    out.append(html.escape(source[cursor:]))
    return "".join(out).rstrip("\n")


def run(script: Path) -> str:
    """Run one example and return what it printed to stdout."""
    result = subprocess.run(  # noqa: S603 — a fixed interpreter on our own scripts
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise SystemExit(f"{script.name} failed:\n{result.stderr}")
    return result.stdout.rstrip("\n")


def main() -> None:
    """Fill the template and write the page."""
    scripts = {path.name[:2]: path for path in sorted(EXAMPLES.glob("[0-9][0-9]_*.py"))}
    outputs = {number: run(path) for number, path in scripts.items()}

    def fill(match: re.Match[str]) -> str:
        kind, number = match.groups()
        script = scripts[number]
        if kind == "example":
            return highlight(script.read_text(encoding="utf-8"))
        if kind == "output":
            return html.escape(outputs[number])
        return f"examples/{script.name}"

    page = PLACEHOLDER.sub(fill, TEMPLATE.read_text(encoding="utf-8"))
    page = page.replace("<!--generated-->", dt.datetime.now(dt.UTC).strftime("%-d %B %Y"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} from {len(scripts)} examples")


if __name__ == "__main__":
    main()
