"""Colab notebooks for the use cases, one per script in examples/.

Each notebook is the example script split into cells, with the request from the page
on top, an install cell first, and a cell that shows the charts and downloads the
files the script saved. They are written without outputs, so they stay small and say
nothing a fresh run would not. ``site/build.py`` writes them on every build, so they
never drift from the scripts.
"""

from __future__ import annotations

import ast
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO = "nerd-factory/undata"
PAGE = "https://nerd-factory.github.io/undata/"
SAVED = re.compile(r"""["']([\w.-]+\.(?:png|html|xlsx|csv))["']""")


@dataclass(frozen=True)
class Case:
    """What the page says about one use case."""

    anchor: str
    title: str
    ask: str


def cases(template: str) -> dict[str, Case]:
    """Read each use case's anchor, title and request from the page template."""
    found = {}
    for anchor, body in re.findall(
        r'<article class="case" id="([^"]+)">(.*?)</article>', template, re.S
    ):
        number = re.search(r"<!--name:(\d\d)-->", body)
        title = re.search(r"<h3>(.*?)</h3>", body, re.S)
        ask = re.search(r'<blockquote class="ask"><p>(.*?)</p>', body, re.S)
        if number and title and ask:
            found[number.group(1)] = Case(anchor, plain(title.group(1)), plain(ask.group(1)))
    return found


def plain(fragment: str) -> str:
    """HTML to one line of text."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def colab_url(path: str) -> str:
    """The link that opens a notebook in this repository, by its repo path, in Google Colab."""
    return f"https://colab.research.google.com/github/{REPO}/blob/main/{path}"


def chunks(code: str) -> list[str]:
    """Split a script at its blank lines, keeping any statement that spans one whole."""
    out: list[str] = []
    pending = ""
    for part in re.split(r"\n\s*\n", code.strip()):
        pending = f"{pending}\n\n{part}" if pending else part
        try:
            ast.parse(pending)
        except SyntaxError:
            continue
        out.append(pending)
        pending = ""
    if pending:
        out.append(pending)
    return out


def write_notebook(script: Path, case: Case, out: Path) -> Path:
    """Write the Colab notebook for one example script and return its path."""
    source = script.read_text(encoding="utf-8")
    module = ast.parse(source)
    summary = ast.get_docstring(module) or ""
    body = source
    if summary:  # the docstring becomes the introduction, not a code cell
        body = "\n".join(source.splitlines()[module.body[0].end_lineno :])
    number = script.name[:2]
    saved = list(dict.fromkeys(SAVED.findall(body)))

    cells = [
        markdown(
            f"# {number} · {case.title}\n\n"
            f"> {case.ask}\n\n"
            f"{summary}\n\n"
            "Run each cell in order with **Shift + Enter** (or the ▶ button). You don't need to "
            "know Python: change the names in quotes to ask your own question. The page shows "
            f"what this code returned on its last run: [use case {number}]({PAGE}#{case.anchor}).\n\n"
            f"It uses [undata]({PAGE}), a free, open-source package for the "
            "[UN System Data Commons](https://data.un.org), which holds statistics from 26 UN "
            "System entities. undata is a personal open-source project, not an official UN "
            "product, and the data belongs to the agencies that publish it."
        ),
        markdown("## Install undata\nThis takes about 20 seconds the first time."),
        code('%pip install -q "undata[charts]"'),
        markdown("## Run the use case"),
        *(code(chunk) for chunk in chunks(body)),
    ]
    if saved:
        cells += [markdown("## What it saved"), code(show_and_download(saved))]
    cells.append(
        markdown(
            "## Where next\n\n"
            f"- **All twelve use cases**, with their output and charts: {PAGE}\n"
            f"- **Your first table in five minutes**, a gentler start: {colab_url('examples/first_table.ipynb')}\n"
            f"- **Every function explained**: {PAGE}reference/\n"
            "- **Something didn't work, or you need an indicator we don't cover?** Open an issue: "
            f"https://github.com/{REPO}/issues\n\n"
            "Created and maintained by Mafizul Islam · MIT licence"
        )
    )
    for i, cell in enumerate(cells):
        cell["id"] = f"{number}-{i:02d}"  # fixed ids, so a rebuild changes nothing it needn't

    notebook = {
        "cells": cells,
        "metadata": {
            "colab": {"name": f"undata {number}: {case.title}", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = out / script.with_suffix(".ipynb").name
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def show_and_download(saved: list[str]) -> str:
    """Code that shows the saved charts and, in Colab, downloads every saved file."""
    lines = []
    if any(name.endswith(".png") for name in saved):
        lines += ["from IPython.display import Image, display", ""]
        lines += [f'display(Image("{name}"))' for name in saved if name.endswith(".png")]
        lines.append("")
    lines += [
        "try:",
        "    from google.colab import files  # only exists in Colab",
        "",
        *(f'    files.download("{name}")' for name in saved),
        "except ImportError:",
        f'    print("Saved {", ".join(saved)} next to this notebook.")',
    ]
    return "\n".join(lines)


def markdown(text: str) -> dict:
    """A markdown cell."""
    return {"cell_type": "markdown", "metadata": {}, "source": lines_of(text)}


def code(text: str) -> dict:
    """An empty-output code cell."""
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines_of(text),
    }


def lines_of(text: str) -> list[str]:
    """Notebook JSON keeps a cell's source as a list of lines."""
    return text.strip("\n").splitlines(keepends=True)
