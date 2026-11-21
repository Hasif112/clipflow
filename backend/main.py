import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pipeline.engine import run_engine

app = FastAPI(title="ClipFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA = Path("outputs/projects")
DATA.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=DATA), name="files")

ALLOWED = {".mov", ".mp4", ".m4v"}

# Job status lives in memory for now. Moves to a real database when we deploy.
JOBS: dict[str, dict] = {}


def process_project(project_id: str, source: Path, project_dir: Path) -> None:
    """Runs in the background after the upload request has already returned."""
    job = JOBS[project_id]

    def on_progress(message, fraction, reel=None):
        job["message"] = message
        job["progress"] = round(fraction, 2)
        if reel:
            job["reels"].append(f"/files/{project_id}/reels/{reel.name}")

    try:
        job["status"] = "processing"
        run_engine(str(source), project_dir, on_progress)
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["message"] = f"Something went wrong: {e}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/projects")
def create_project(background: BackgroundTasks, video: UploadFile = File(...)):
    ext = Path(video.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use .mov or .mp4")

    project_id = uuid.uuid4().hex[:8]
    project_dir = DATA / project_id
    project_dir.mkdir(parents=True)

    source = project_dir / f"source{ext}"
    with source.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    JOBS[project_id] = {"status": "queued", "message": "Upload received", "progress": 0.0, "reels": []}
    background.add_task(process_project, project_id, source, project_dir)
    return {"project_id": project_id}


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    job = JOBS.get(project_id)
    if not job:
        raise HTTPException(404, "Project not found")
    return job