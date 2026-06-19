"""Serve a single vertical behind its own FastAPI app.

This uses the vertical's built-in service entrypoint, which exposes the
vertical's graphs over HTTP. Configure the model with AG_LLM_PROVIDER /
AG_LLM_MODEL and the provider key, and protect the API with AG_API_KEY.

    uv run --all-packages python examples/embed_in_fastapi.py
"""
import uvicorn
from agentgraph_sales_ops.service import SalesOpsService, _build_app


def main() -> None:
    svc = SalesOpsService.default()
    app = _build_app(svc)
    uvicorn.run(app, host="0.0.0.0", port=8081)


if __name__ == "__main__":
    main()
