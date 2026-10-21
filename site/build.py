"""Build the use-cases page from site/template.html and the scripts in examples/.

Every "works today" block on the page is the exact source of an example script, and
every output block is what that script printed when this ran. Run it from the repo
root with network access:

    uv run python site/build.py

It writes site/public/index.html, which is committed; deploying needs no build step.
Charts an example saves (PNG, and interactive HTML) are copied to site/public/img/
and shown under the example, so the page shows exactly what the code made. It also
writes a Colab notebook for each example to examples/colab/, which the page links to.
"""

from __future__ import annotations

import datetime as dt
import html
import io
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

from charts import render_chart
from colab import cases, colab_url, write_notebook

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
TEMPLATE = ROOT / "site" / "template.html"
OUTPUT = ROOT / "site" / "public" / "index.html"
IMAGES = OUTPUT.parent / "img"
NOTEBOOKS = EXAMPLES / "colab"

PLACEHOLDER = re.compile(r"<!--(example|output|name|chart|figure|report|colab):(\d\d)-->")


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


def keep_figures(number: str, workdir: Path) -> list[str]:
    """Copy the charts example ``number`` saved into the site; return their names."""
    kept = []
    for made in sorted(workdir.glob("*")):
        if made.suffix in (".png", ".html"):
            name = f"{number}-{made.name}"
            shutil.copyfile(made, IMAGES / name)
            kept.append(name)
    return kept


def figure(names: list[str], alt: str) -> str:
    """An image of the saved chart, with a link to its interactive version if there is one."""
    png = next((n for n in names if n.endswith(".png")), None)
    if png is None:
        raise SystemExit(f"no chart was saved for {names}")
    out = f'<img src="img/{png}" alt="{html.escape(alt, quote=True)}" loading="lazy">'
    for page in (n for n in names if n.endswith(".html")):
        out += f'<figcaption><a href="img/{page}">Open the interactive version</a>: hover for every number.</figcaption>'
    return out


def main() -> None:
    """Fill the template and write the page."""
    scripts = {path.name[:2]: path for path in sorted(EXAMPLES.glob("[0-9][0-9]_*.py"))}
    template = TEMPLATE.read_text(encoding="utf-8")
    described = cases(template)
    if missing := sorted(set(scripts) - set(described)):
        raise SystemExit(f"no use case on the page for examples {', '.join(missing)}")
    NOTEBOOKS.mkdir(exist_ok=True)
    notebooks = {
        number: write_notebook(path, described[number], NOTEBOOKS)
        for number, path in scripts.items()
    }
    shutil.rmtree(IMAGES, ignore_errors=True)
    IMAGES.mkdir(parents=True)
    outputs: dict[str, str] = {}
    figures: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory() as scratch:
        for number, path in scripts.items():
            workdir = Path(scratch) / number
            workdir.mkdir()
            outputs[number] = run(path, workdir)
            figures[number] = keep_figures(number, workdir)

    def report(number: str) -> str:
        return outputs[number].split("\n\n")[-1].strip()

    def fill(match: re.Match[str]) -> str:  # noqa: PLR0911 — one return per placeholder
        kind, number = match.groups()
        script = scripts[number]
        if kind == "example":
            return highlight(script.read_text(encoding="utf-8"))
        if kind == "output":
            return html.escape(outputs[number])
        if kind == "report":
            return html.escape(report(number))
        if kind == "chart":
            return render_chart(number)
        if kind == "figure":
            return figure(figures[number], report(number))
        if kind == "colab":
            return colab_url(notebooks[number].relative_to(ROOT).as_posix())
        return f"examples/{script.name}"

    page = PLACEHOLDER.sub(fill, template)
    page = page.replace("<!--generated-->", dt.datetime.now(dt.UTC).strftime("%-d %B %Y"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    print(
        f"wrote {OUTPUT.relative_to(ROOT)} from {len(scripts)} examples, "
        f"and {len(notebooks)} notebooks to {NOTEBOOKS.relative_to(ROOT)}/"
    )


if __name__ == "__main__":
    main()
