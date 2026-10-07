from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.sse import sse
from app.errors import AppError
from app.llm.options import GenParams
from app.services.engine import collect

router = APIRouter()


class SummarizeIn(BaseModel):
    rel_path: str
    style: str = "short"
    params: GenParams = Field(default_factory=GenParams)
    prompt_name: str | None = None
    prompt_body: str | None = None


class ExtractIn(BaseModel):
    rel_path: str
    schema_name: str = "entities"
    params: GenParams = Field(default_factory=GenParams)
    prompt_body: str | None = None


class TransformIn(BaseModel):
    rel_path: str | None = None
    text: str | None = None
    action: str
    tone: str | None = None
    target_language: str | None = None
    params: GenParams = Field(default_factory=GenParams)
    prompt_name: str | None = None
    prompt_body: str | None = None


class StreamIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    params: GenParams = Field(default_factory=GenParams)


class CompareSide(BaseModel):
    task: str = "summarize"  # summarize | transform
    rel_path: str
    style: str = "short"
    action: str | None = None
    tone: str | None = None
    target_language: str | None = None
    prompt_name: str | None = None
    prompt_body: str | None = None
    params: GenParams = Field(default_factory=GenParams)


class CompareIn(BaseModel):
    run_a_inputs: CompareSide
    run_b_inputs: CompareSide


@router.post("/stream")
async def stream(request: Request, body: StreamIn):
    """M3: send a raw prompt to the model and stream tokens back (also handy for debugging connectivity)."""
    return sse(request.app.state.container.engine.raw_stream(body.prompt, body.params))


@router.post("/summarize")
async def summarize(request: Request, body: SummarizeIn):
    e = request.app.state.container.engine
    return sse(await e.summarize(body.rel_path, None, body.style, body.params, body.prompt_name, body.prompt_body))


@router.post("/extract")
async def extract(request: Request, body: ExtractIn) -> dict:
    return await request.app.state.container.engine.extract(
        body.rel_path, None, body.schema_name, body.params, body.prompt_body
    )


@router.post("/transform")
async def transform(request: Request, body: TransformIn):
    e = request.app.state.container.engine
    return sse(
        await e.transform(
            body.action,
            body.rel_path,
            body.text,
            body.tone,
            body.target_language,
            body.params,
            body.prompt_name,
            body.prompt_body,
        )
    )


@router.post("/compare")
async def compare(request: Request, body: CompareIn) -> dict:
    """Run two prompt/parameter variants on the same document and return both results."""
    e = request.app.state.container.engine

    async def run(side: CompareSide) -> dict:
        if side.task == "summarize":
            ev = await e.summarize(side.rel_path, None, side.style, side.params, side.prompt_name, side.prompt_body)
        elif side.task == "transform":
            if not side.action:
                raise AppError("MISSING_INPUT", "transform requires 'action'", 422)
            ev = await e.transform(
                side.action,
                side.rel_path,
                None,
                side.tone,
                side.target_language,
                side.params,
                side.prompt_name,
                side.prompt_body,
            )
        else:
            raise AppError("BAD_TASK", "task must be 'summarize' or 'transform'", 422)
        return await collect(ev)

    return {"a": await run(body.run_a_inputs), "b": await run(body.run_b_inputs)}
