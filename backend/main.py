import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from pipeline.engine import run_engine

app = FastAPI(title="ClipFlow API")

DATA = Path("outputs/projects")
DATA.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=DATA), name="files")

ALLOWED = {".mov", ".mp4", ".m4v"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/projects")
def create_project(video: UploadFile = File(...)):
    ext = Path(video.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use .mov or .mp4")

    project_id = uuid.uuid4().hex[:8]
    project_dir = DATA / project_id
    project_dir.mkdir(parents=True)

    source = project_dir / f"source{ext}"
    with source.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    reels = run_engine(str(source), project_dir)
    return {
        "project_id": project_id,
        "reels": [f"/files/{project_id}/reels/{p.name}" for p in reels],
    }