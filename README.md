# Meeting Summarizer

An AI-powered tool that turns raw meeting audio into a clean, actionable summary. Upload a recording and get back a full transcript, a plain-English summary, the key decisions made, and a structured action items list — each with an owner and due date where mentioned.

Built for teams who don't have time to re-listen to a 45-minute call just to find out what they agreed to.

## What it does

1. **You upload an audio recording** of a meeting through a simple web page.
2. **The audio is transcribed** into text using a speech-to-text (ASR) model.
3. **The transcript is passed to an LLM**, which extracts a summary, the key decisions made, and a list of action items with owners and deadlines.
4. **Everything is saved and displayed** in the browser, and you can revisit any past meeting from a history list.

## Features
- 🎧 Upload meeting audio (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.webm`, `.ogg`, `.flac`)
- 📝 Automatic transcription via Whisper (through Groq's free API, OpenAI's API, or fully offline)
- 🤖 LLM-generated summary, key decisions, and action items (Groq, Claude, or GPT — your choice)
- 💾 Persistent storage of past meetings (SQLite)
- 🌐 Simple web frontend to upload audio and browse results — no separate setup needed
- 🔌 Pluggable architecture — swap ASR or LLM providers by changing one environment variable

## Tech Stack
- **Backend:** Python, FastAPI, SQLAlchemy (SQLite)
- **Transcription:** Whisper (via Groq, OpenAI, or a local model)
- **Summarization:** LLM APIs (Groq / Anthropic Claude / OpenAI GPT)
- **Frontend:** Plain HTML, CSS, and JavaScript (no build step required)

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
- An API key for transcription and summarization. The easiest free option is [Groq](https://console.groq.com) (no credit card needed) — it covers both. Alternatives: OpenAI, Anthropic (Claude), or Azure Speech.

## 2. Setup

```bash
cd meeting-summarizer/backend
python -m venv venv
source venv/bin/activate        # Windows (PowerShell): venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy the example environment file and fill in your key:
```bash
cp .env.example .env
```

Edit `.env` — the simplest setup (recommended, free) uses Groq for both steps:
```
ASR_PROVIDER=openai_whisper_api      # or local_whisper / azure
LLM_PROVIDER=anthropic               # or openai

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```


> **Using local Whisper instead of a cloud API?**
> Uncomment `openai-whisper` and `ffmpeg-python` in `requirements.txt`, install ffmpeg on your system (`brew install ffmpeg` / `apt install ffmpeg`), then set `ASR_PROVIDER=local_whisper` in `.env`. No API key needed for transcription in that case.

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

## 8. Project Structure & Design Notes

The codebase is intentionally split into clean, single-responsibility layers:

- **`asr.py`** — handles all speech-to-text logic. Each provider (Groq, OpenAI, local Whisper, Azure) is a separate function, selected at runtime by the `ASR_PROVIDER` variable.
- **`summarizer.py`** — handles all LLM summarization logic, same pattern as above via `LLM_PROVIDER`. The prompt that instructs the LLM how to summarize lives in `SYSTEM_PROMPT` at the top of this file and can be tuned without touching any other code.
- **`database.py`** — defines the SQLite schema and session handling for storing meeting records.
- **`app.py`** — the FastAPI layer that ties everything together and exposes the HTTP API.
- **`frontend/`** — a dependency-free HTML/CSS/JS page that talks to the API and is served automatically by the backend.

This separation means adding a new transcription or summarization provider (e.g. Deepgram, Gemini) only requires adding one function and one line to a dispatcher — no changes anywhere else.
