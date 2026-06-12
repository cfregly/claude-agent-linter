"""Load MCP tool definitions from a JSON file or a live FastMCP server module.

Accepted JSON shapes (all equivalent):
  [ {name, description, inputSchema}, ... ]          # bare list
  { "tools": [ ... ] }                                # tools/list response body
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_tools(path: str) -> list[dict]:
    p = Path(path)
    if p.suffix == ".py":
        return _load_from_fastmcp(p)
    data = json.loads(p.read_text())
    tools = data["tools"] if isinstance(data, dict) else data
    if not isinstance(tools, list):
        raise ValueError(f"{path}: expected a list of tools or {{'tools': [...]}}")
    return tools


def _load_from_fastmcp(path: Path) -> list[dict]:
    """Import a FastMCP server module and extract its registered tools.

    Requires the `mcp` package (and the module's own imports) to be available.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Loading from a .py server requires the 'mcp' package "
            "(pip install mcp). Alternatively, dump tools/list to JSON."
        ) from exc

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)

    server = next(
        (v for v in vars(module).values() if isinstance(v, FastMCP)), None
    )
    if server is None:
        raise SystemExit(f"{path}: no FastMCP instance found at module top level")

    tools = []
    for t in server._tool_manager.list_tools():
        tools.append({
            "name": t.name,
            "description": t.description or "",
            "inputSchema": t.parameters,
        })
    return tools
