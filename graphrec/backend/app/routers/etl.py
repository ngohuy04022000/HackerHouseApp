import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.etl.etl_pipeline import run_etl

router   = APIRouter()
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Lưu trạng thái ETL để frontend polling
ETL_STATUS: dict = {"running": False, "last": None}


async def _run_task(paths: list[str], n_users: int, n_actions: int) -> None:
    """Background task wrapper – cập nhật ETL_STATUS."""
    ETL_STATUS["running"] = True
    try:
        result = await run_etl(paths, n_users=n_users, n_actions=n_actions)
        ETL_STATUS["last"] = {"status": "ok", **result}
    except Exception as exc:
        ETL_STATUS["last"] = {"status": "error", "msg": str(exc)}
    finally:
        ETL_STATUS["running"] = False


@router.post("/upload")
async def upload_csv(
    background_tasks: BackgroundTasks,
    files:    list[UploadFile] = File(...),
    n_users:   int = Form(200),
    n_actions: int = Form(5000),
):
    """Upload một hoặc nhiều file CSV rồi khởi động ETL ngầm."""
    if ETL_STATUS["running"]:
        return JSONResponse({"error": "ETL dang chay, vui long cho."}, status_code=409)

    saved = []
    for f in files:
        dest = DATA_DIR / f.filename
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(str(dest))

    background_tasks.add_task(_run_task, saved, n_users, n_actions)
    return {"message": "ETL started", "files": [f.filename for f in files]}


@router.get("/status")
async def etl_status():
    return ETL_STATUS


@router.get("/datasets")
async def list_datasets():
    """Liệt kê file CSV trong thư mục /app/data."""
    return {"datasets": [p.name for p in DATA_DIR.glob("*.csv")]}


class RunExistingRequest(BaseModel):
    filenames: list[str]
    n_users:   int = 200
    n_actions: int = 5000


@router.post("/run-existing")
async def run_existing(background_tasks: BackgroundTasks, req: RunExistingRequest):
    """Chạy lại ETL trên file CSV đã upload trước đó."""
    if ETL_STATUS["running"]:
        return JSONResponse({"error": "ETL dang chay."}, status_code=409)

    paths   = [str(DATA_DIR / fn) for fn in req.filenames]
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        return JSONResponse({"error": f"File khong ton tai: {missing}"}, status_code=404)

    background_tasks.add_task(_run_task, paths, req.n_users, req.n_actions)
    return {"message": "ETL started", "files": req.filenames}
