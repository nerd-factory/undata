"""Build the use-cases page from site/template.html and the scripts in examples/.

Every "works today" block on the page is the exact source of an example script, and
every output block is what that script printed when this ran. Run it from the repo
root with network access:

    uv run python site/build.py

It writes site/public/index.html, which is committed; deploying needs no build step.
"""

from __future__ import annotations

import datetime as dt
import html
import io
import re
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

from charts import render_chart

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
TEMPLATE = ROOT / "site" / "template.html"
OUTPUT = ROOT / "site" / "public" / "index.html"

PLACEHOLDER = re.compile(r"<!--(example|output|name|chart|report):(\d\d)-->")


def highlight(source: str) -> str:
    """Escape Python source for HTML, wrapping comments and docstrings in spans."""
    spans: list[tuple[tuple[int, int], tuple[int, int], str]] = []
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    starts_line = True
    for i, token in enumerate(tokens):
        if token.type == tokenize.COMMENT:
            spans.append((token.start, token.end, "c"))
        elif token.type == tokenize.STRING and starts_line:
            following = next(
                (t for t in tokens[i + 1 :] if t.type not in (tokenize.COMMENT, tokenize.NL)), None
            )
            if following is None or following.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                spans.append((token.start, token.end, "c"))  # a docstring statement
        if token.type in (tokenize.NEWLINE, tokenize.NL):
            starts_line = True
        elif token.type not in (tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
            starts_line = False

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


def run(script: Path, workdir: Path) -> str:
    """Run one example and return what a user would see: output and warnings, in order.

    It runs in a scratch directory, so examples that save files leave nothing behind,
    and the scratch path is trimmed from warning locations.
    """
    result = subprocess.run(  # noqa: S603 — a fixed interpreter on our own scripts
        [sys.executable, "-u", str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=180,
        cwd=workdir,
    )
    if result.returncode != 0:
        raise SystemExit(f"{script.name} failed:\n{result.stdout}")
    return result.stdout.replace(f"{EXAMPLES}/", "").rstrip("\n")


def main() -> None:
    """Fill the template and write the page."""
    scripts = {path.name[:2]: path for path in sorted(EXAMPLES.glob("[0-9][0-9]_*.py"))}
    with tempfile.TemporaryDirectory() as scratch:
        outputs = {number: run(path, Path(scratch)) for number, path in scripts.items()}

    def fill(match: re.Match[str]) -> str:
        kind, number = match.groups()
        script = scripts[number]
        if kind == "example":
            return highlight(script.read_text(encoding="utf-8"))
        if kind == "output":
            return html.escape(outputs[number])
        if kind == "report":
            return html.escape(outputs[number].split("\n\n")[-1].strip())
        if kind == "chart":
            return render_chart(number)
        return f"examples/{script.name}"

    page = PLACEHOLDER.sub(fill, TEMPLATE.read_text(encoding="utf-8"))
    page = page.replace("<!--generated-->", dt.datetime.now(dt.UTC).strftime("%-d %B %Y"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} from {len(scripts)} examples")


if __name__ == "__main__":
    main()
