"""claude-agent-linter — turn vague MCP tools into contract-grade agent interfaces."""

from .rules import grade, lint_server, lint_tool, score_tool  # noqa: F401

__version__ = "0.1.0"
