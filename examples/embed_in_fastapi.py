"""Embed the runtime in a FastAPI app and run a vertical."""
import uvicorn

from agentgraph_sales_ops import SalesOpsService


def main() -> None:
    svc = SalesOpsService.default()
    app = svc.build_app()  # type: ignore[attr-defined]
    # The vertical Service provides a default FastAPI app; we extend it
    # with a /run/lead route.
    from fastapi import HTTPException
    from pydantic import BaseModel

    class Body(BaseModel):
        contact_email: str

    @app.post("/run/lead")
    async def run_lead(body: Body) -> dict:
        if not body.contact_email:
            raise HTTPException(400, "contact_email required")
        return svc.run_lead(contact_email=body.contact_email).to_dict()

    uvicorn.run(app, host="0.0.0.0", port=8081)


if __name__ == "__main__":
    main()
