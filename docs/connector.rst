The AI connector (MCP)
======================

``undata-mcp`` is a `Model Context Protocol <https://modelcontextprotocol.io>`_ server: it
lets an AI assistant such as Claude search UN indicators, fetch data and run the analyses
itself. Every tool only reads, and needs no account or key. Answers carry a table, a
summary sentence, the data-quality notes and the sources; analysis tools can attach their
chart as an image.

Setting it up
-------------

Install `uv <https://docs.astral.sh/uv/getting-started/installation/>`_, which fetches
Python and the package on first use.

**Claude Desktop.** *Settings → Developer → Edit Config*, then add, and restart:

.. code-block:: json

   {
     "mcpServers": {
       "undata": {"command": "uvx", "args": ["--from", "undata[mcp]", "undata-mcp"]}
     }
   }

**Claude Code.**

.. code-block:: bash

   claude mcp add undata -- uvx --from "undata[mcp]" undata-mcp

**Other clients.** ``pip install "undata[mcp]"``, then run ``undata-mcp`` (stdio), or
``undata-mcp --http`` to serve Streamable HTTP at ``http://127.0.0.1:8000/mcp``
(``--host``, ``--port``). Responses are cached on disk; ``--no-cache`` turns that off.

Things to ask
-------------

- "Which least developed countries are on track to bring maternal mortality below 70 by
  2030? Show me a chart."
- "Give me a one-page profile of Chad against Middle Africa and the world."
- "How wide is the rural-urban gap in primary school completion in the Sahel?"
- "Which countries in Western Africa have reported electricity access in the last five
  years?"

Tools
-----

Generated from the server, so it lists exactly what the installed version offers.

.. include:: _generated/mcp_tools.rst
