from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/prompts")


class PromptIn(BaseModel):
    body: str
    note: str | None = None


class PreviewIn(BaseModel):
    body: str | None = None


@router.get("")
def list_prompts(request: Request) -> dict:
    return {"prompts": request.app.state.container.prompts.list_all()}


@router.get("/{name}")
def get_prompt(request: Request, name: str) -> dict:
    return request.app.state.container.prompts.get(name)


@router.put("/{name}")
def put_prompt(request: Request, name: str, body: PromptIn) -> dict:
    """Saving never overwrites history: it creates the next version (and rewrites the .md file)."""
    return request.app.state.container.prompts.save(name, body.body, body.note)


@router.get("/{name}/versions")
def versions(request: Request, name: str) -> dict:
    return {"versions": request.app.state.container.prompts.versions(name)}


@router.post("/{name}/restore/{version}")
def restore(request: Request, name: str, version: int) -> dict:
    return request.app.state.container.prompts.restore(name, version)


@router.post("/{name}/preview")
def preview(request: Request, name: str, body: PreviewIn | None = None) -> dict:
    return request.app.state.container.prompts.preview(name, body.body if body else None)
