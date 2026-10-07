from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/models")
async def list_models(request: Request) -> dict:
    c = request.app.state.container
    return {"models": await c.llm.models(), "default": c.llm.default_model}
