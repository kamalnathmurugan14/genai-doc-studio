from fastapi import APIRouter, Request

router = APIRouter(prefix="/runs")


@router.get("")
def list_runs(request: Request, task: str = "", file: str = "", limit: int = 100) -> dict:
    return {"runs": request.app.state.container.runs.list_all(task, file, min(max(limit, 1), 500))}


@router.get("/{run_id}")
def get_run(request: Request, run_id: int) -> dict:
    return request.app.state.container.runs.get(run_id)
