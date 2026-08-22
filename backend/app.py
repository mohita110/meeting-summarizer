"""
Meeting Summarizer API
----------------------
Endpoints:
  POST /api/meetings/upload   -> upload audio, transcribe + summarize, store result
  GET  /api/meetings          -> list all meetings (most recent first)
  GET  /api/meetings/{id}     -> get full detail for one meeting
  DELETE /api/meetings/{id}   -> delete a meeting record

Run with:
  uvicorn app:app --reload --port 8000
"""
import os
import json
import shutil
import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import init_db, get_db, Meeting
import asr
import summarizer

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Meeting Summarizer API", version="1.0.0")

# Allow the frontend (served separately or opened as a local file) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/meetings/upload")
async def upload_meeting(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # Save upload to disk with a unique name to avoid collisions.
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(dest_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        os.remove(dest_path)
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_UPLOAD_MB}MB limit")

    meeting = Meeting(filename=file.filename, status="processing")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    try:
        transcript_text = asr.transcribe(dest_path)
        result = summarizer.summarize(transcript_text)

        meeting.transcript = transcript_text
        meeting.summary = result.get("summary", "")
        meeting.key_decisions = json.dumps(result.get("key_decisions", []))
        meeting.action_items = json.dumps(result.get("action_items", []))
        meeting.status = "done"
    except (asr.TranscriptionError, summarizer.SummarizationError) as e:
        meeting.status = "failed"
        meeting.error = str(e)
    finally:
        db.commit()
        db.refresh(meeting)
        # Clean up the stored audio file once processed (comment out to keep raw audio).
        if os.path.exists(dest_path):
            os.remove(dest_path)

    return _serialize(meeting)


@app.get("/api/meetings")
def list_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
    return [_serialize(m) for m in meetings]


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return _serialize(meeting)


@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    db.delete(meeting)
    db.commit()
    return {"deleted": meeting_id}


def _serialize(m: Meeting) -> dict:
    return {
        "id": m.id,
        "filename": m.filename,
        "status": m.status,
        "transcript": m.transcript,
        "summary": m.summary,
        "key_decisions": json.loads(m.key_decisions) if m.key_decisions else [],
        "action_items": json.loads(m.action_items) if m.action_items else [],
        "error": m.error,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# Optionally serve the static frontend directly from FastAPI at "/"
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
