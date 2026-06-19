"""AgentGraph command-line interface.

Top-level commands:

- ag version
- ag serve            start the HTTP server
- ag run <agent>      run a registered agent (against a running server)
- ag threads          list threads on a server
- ag audit            query audit log
"""
from agentgraph_cli.cli import main

__all__ = ["main"]
