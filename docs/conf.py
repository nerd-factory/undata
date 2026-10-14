"""Sphinx configuration for undata's API reference.

Build it with ``uv run --group docs sphinx-build -W docs site/public/reference``. The
connector's tool list and the command-line help are generated from the code each time,
so they cannot drift from what the package does.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

import undata  # noqa: E402

project = "undata"
author = "Mafizul Islam"
copyright = "2026, Mafizul Islam"
release = undata.__version__
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_rtype = False
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"
autodoc_member_order = "bysource"
autodoc_default_options = {"members": False}
add_module_names = False
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
}
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

html_theme = "furo"
html_title = "undata reference"
html_baseurl = "https://nerd-factory.github.io/undata/reference/"
html_static_path: list[str] = []
html_show_sourcelink = False
html_theme_options = {
    "source_repository": "https://github.com/nerd-factory/undata",
    "source_branch": "main",
    "source_directory": "docs/",
    "light_css_variables": {"color-brand-primary": "#0072B2", "color-brand-content": "#0072B2"},
    "dark_css_variables": {"color-brand-primary": "#56B4E9", "color-brand-content": "#56B4E9"},
}
exclude_patterns = ["_build"]


# ── Pages generated from the code ───────────────────────────────────────

GENERATED = HERE / "_generated"
GENERATED.mkdir(exist_ok=True)
(GENERATED / ".gitignore").write_text("# Written by conf.py on every build\n*\n", encoding="utf-8")


def _cli_help() -> str:
    """``undata --help`` and each command's help, as literal blocks."""
    from undata.cli import _parser  # noqa: PLC0415

    parser = _parser()
    commands = next(a for a in parser._actions if a.dest == "command")
    blocks = [("undata", parser.format_help())]
    blocks += [(f"undata {name}", sub.format_help()) for name, sub in commands.choices.items()]  # type: ignore[union-attr]
    out = []
    for title, text in blocks:
        out += [title, "-" * len(title), "", ".. code-block:: text", ""]
        out += [f"   {line}" if line else "" for line in text.splitlines()]
        out.append("")
    return "\n".join(out)


def _schema_type(spec: dict) -> str:
    if "anyOf" in spec:
        return (
            " or ".join(_schema_type(s) for s in spec["anyOf"] if s.get("type") != "null")
            + " (optional)"
        )
    if spec.get("enum"):
        return " | ".join(f'"{v}"' for v in spec["enum"])
    if spec.get("type") == "array":
        return f"list of {_schema_type(spec.get('items', {}))}"
    return {
        "string": "text",
        "integer": "whole number",
        "number": "number",
        "boolean": "true/false",
    }.get(spec.get("type", ""), spec.get("type", ""))


def _mcp_tools() -> str:
    """Every connector tool: what it does and its arguments, read from the server itself."""
    try:
        from undata.mcp_server import server  # noqa: PLC0415
    except ImportError:  # pragma: no cover - the docs group installs mcp
        return "Install the ``mcp`` extra to list the tools here."
    with contextlib.redirect_stderr(io.StringIO()):
        tools = asyncio.run(server.list_tools())
    out = []
    for tool in tools:
        heading = f"{tool.title or tool.name}"
        out += [heading, "~" * len(heading), "", f"``{tool.name}``", ""]
        out += [
            line.strip() if line.startswith("    ") else line
            for line in (tool.description or "").splitlines()
        ]
        out += [
            "",
            ".. list-table::",
            "   :header-rows: 1",
            "   :widths: 20 25 55",
            "",
            "   * - Argument",
            "     - Type",
            "     - Meaning",
        ]
        schema = tool.input_schema or {}
        required = set(schema.get("required", []))
        for name, spec in schema.get("properties", {}).items():
            meaning = spec.get("description", "")
            if name not in required and "default" in spec:
                meaning = f"{meaning} Default: ``{spec['default']!r}``.".strip()
            if name in required:
                meaning = f"**Required.** {meaning}"
            out += [f"   * - ``{name}``", f"     - {_schema_type(spec)}", f"     - {meaning}"]
        out.append("")
    return "\n".join(out)


(GENERATED / "cli.rst").write_text(_cli_help(), encoding="utf-8")
(GENERATED / "mcp_tools.rst").write_text(_mcp_tools(), encoding="utf-8")
