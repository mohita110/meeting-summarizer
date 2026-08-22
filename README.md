# Meeting Summarizer

Transcribe meeting audio and generate action-oriented summaries: transcript + summary + key decisions + action items, with a simple web frontend to upload audio and view results.

## Features
- 🎧 Upload meeting audio (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.webm`, `.ogg`, `.flac`)
- 📝 Automatic transcription (OpenAI Whisper API, local Whisper, or Azure Speech)
- 🤖 LLM-generated summary, key decisions, and action items (Claude or GPT)
- 💾 Persistent storage of past meetings (SQLite)
- 🌐 Minimal frontend to upload audio and browse results

## Project Structure
```
meeting-summarizer/
├── backend/
│   ├── app.py            # FastAPI app & routes
│   ├── asr.py             # Speech-to-text integrations
│   ├── summarizer.py      # LLM summary generation
│   ├── database.py        # SQLite models
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

## 1. Prerequisites
- Python 3.10+
- An API key for at least one ASR provider and one LLM provider:
  - **ASR**: OpenAI (for Whisper API) or Azure Speech, *or* no key at all if using local Whisper
  - **LLM**: Anthropic (Claude) or OpenAI

## 2. Setup

```bash
cd meeting-summarizer/backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example environment file and fill in your keys:
```bash
cp .env.example .env
```

Edit `.env`:
```
ASR_PROVIDER=openai_whisper_api      # or local_whisper / azure
LLM_PROVIDER=anthropic               # or openai

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

> **Using local Whisper instead of a cloud API?**
> Uncomment `openai-whisper` and `ffmpeg-python` in `requirements.txt`, install ffmpeg on your system (`brew install ffmpeg` / `apt install ffmpeg`), then set `ASR_PROVIDER=local_whisper` in `.env`. No OpenAI key needed for transcription in that case.

## 3. Run the app

```bash
cd backend
uvicorn app:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser — the FastAPI backend automatically serves the frontend too.

(If you'd rather host the frontend separately, e.g. with `python -m http.server` from the `frontend/` folder, just set `API_BASE` at the top of `frontend/script.js` to your backend's URL, e.g. `http://localhost:8000`.)

## 4. Using it
1. Click **Choose Audio File** and select a meeting recording.
2. Click **Upload & Process**. This takes a while for longer files (waiting on transcription + LLM call).
3. View the generated **summary**, **key decisions**, and **action items** table.
4. Expand **View Full Transcript** for the raw transcript.
5. Past meetings persist and appear in the **Past Meetings** list — click any to reload its results.

## 5. API Reference

| Method | Endpoint                     | Description                          |
|--------|-------------------------------|---------------------------------------|
| POST   | `/api/meetings/upload`        | Upload audio, returns full result     |
| GET    | `/api/meetings`                | List all past meetings                |
| GET    | `/api/meetings/{id}`           | Get one meeting's full detail         |
| DELETE | `/api/meetings/{id}`           | Delete a meeting record               |
| GET    | `/api/health`                  | Health check                          |

Example curl:
```bash
curl -X POST http://localhost:8000/api/meetings/upload \
  -F "file=@sample_meeting.mp3"
```

## 6. Swapping providers
The ASR and LLM integrations are isolated in `asr.py` and `summarizer.py` behind a single `transcribe()` / `summarize()` function each. To add a new provider (e.g. Deepgram, Google Speech-to-Text, Gemini):
1. Add a new `_transcribe_<provider>()` / `_summarize_<provider>()` function.
2. Add a new branch in the dispatcher (`transcribe()` / `summarize()`).
3. Reference it via the `ASR_PROVIDER` / `LLM_PROVIDER` env var — no other code changes needed.

## 7. Deploying
- **Backend**: any Python host (Render, Railway, Fly.io, EC2, etc). Set the same env vars from `.env` in your host's dashboard/secrets manager instead of a local `.env` file.
- **Database**: SQLite is fine for a demo/small team; swap `DATABASE_URL` in `.env` for a Postgres URL (e.g. `postgresql://user:pass@host/db`) for production — SQLAlchemy handles the rest.
- **Frontend**: since FastAPI serves it as static files by default, no separate deployment step is needed. For a standalone deploy, any static host (Netlify, Vercel, S3) works — just set `API_BASE` in `script.js`.

## 8. Recording a demo video
A simple flow to capture for your demo/deliverable:
1. Show the upload UI and select a short sample meeting recording.
2. Show the processing state, then the resulting transcript, summary, decisions, and action items.
3. Show the "Past Meetings" list persisting across a page reload.
4. Briefly show `asr.py` / `summarizer.py` to demonstrate the pluggable provider design.

## Notes on Evaluation Focus (per project spec)
- **Transcription accuracy**: depends on chosen ASR provider/model size — use `medium`/`large` local Whisper models or the hosted API for best accuracy.
- **Summary quality / prompt effectiveness**: prompt lives in `summarizer.py::SYSTEM_PROMPT` — tune it there.
- **Code structure**: ASR, summarization, storage, and API layers are fully decoupled for easy testing/swapping.
