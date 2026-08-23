"""
ASR (Automatic Speech Recognition) integration.

Supports four interchangeable providers, selected via the ASR_PROVIDER
env var:
  - openai_whisper_api : Whisper via OpenAI's hosted API (simplest, no GPU needed)
  - groq                : Whisper via Groq's free, OpenAI-compatible API
  - local_whisper       : Whisper running locally (offline, needs openai-whisper installed)
  - azure               : Azure Cognitive Services Speech-to-Text

Swap providers without touching any other part of the app.

All audio is preprocessed (noise reduction + normalization + resampling)
before transcription to improve accuracy, especially on noisy recordings.
"""
import os
import subprocess
import tempfile

WHISPER_CONTEXT_PROMPT = (
    "This is a business meeting recording. It may include multiple speakers, "
    "names, dates, project names, and technical terms. Transcribe accurately, "
    "including proper nouns and numbers."
)


class TranscriptionError(Exception):
    pass


def _preprocess_audio(file_path: str) -> str:
    """
    Reduce background noise, normalize volume, and standardize the audio
    format (16kHz mono) before sending it to any ASR provider. This alone
    typically improves transcription accuracy more than any other change.

    Falls back silently to the original file if ffmpeg isn't installed,
    so the app still works without it.
    """
    fd, out_path = tempfile.mkstemp(suffix="_processed.wav")
    os.close(fd)

    # highpass: removes low-frequency rumble (AC hum, desk vibration)
    # afftdn: adaptive FFT-based noise reduction (removes steady background hiss/fan noise)
    # loudnorm: normalizes volume so quiet speakers are as audible as loud ones
    audio_filters = "highpass=f=100,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"

    cmd = [
        "ffmpeg", "-y", "-i", file_path,
        "-af", audio_filters,
        "-ar", "16000",  # Whisper is trained on 16kHz audio
        "-ac", "1",       # mono
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        return out_path
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # ffmpeg not installed, or preprocessing failed — use the original file instead
        if os.path.exists(out_path):
            os.remove(out_path)
        return file_path


def transcribe(file_path: str) -> str:
    """Preprocess audio, dispatch to the configured ASR provider, and clean up."""
    provider = os.getenv("ASR_PROVIDER", "openai_whisper_api")
    processed_path = _preprocess_audio(file_path)

    try:
        if provider == "openai_whisper_api":
            return _transcribe_openai_whisper_api(processed_path)
        elif provider == "groq":
            return _transcribe_groq(processed_path)
        elif provider == "local_whisper":
            return _transcribe_local_whisper(processed_path)
        elif provider == "azure":
            return _transcribe_azure(processed_path)
        else:
            raise TranscriptionError(f"Unknown ASR_PROVIDER: {provider}")
    finally:
        if processed_path != file_path and os.path.exists(processed_path):
            os.remove(processed_path)


def _transcribe_openai_whisper_api(file_path: str) -> str:
    """Uses OpenAI's hosted Whisper transcription endpoint."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise TranscriptionError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            prompt=WHISPER_CONTEXT_PROMPT,
        )
    return result.text


def _transcribe_groq(file_path: str) -> str:
    """
    Uses Groq's free, OpenAI-compatible Whisper endpoint (whisper-large-v3).
    Sign up at console.groq.com to get a free API key.
    """
    from openai import OpenAI

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise TranscriptionError("GROQ_API_KEY is not set")

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file,
            prompt=WHISPER_CONTEXT_PROMPT,
        )
    return result.text


def _transcribe_local_whisper(file_path: str) -> str:
    """
    Uses the open-source `openai-whisper` package to transcribe fully offline.
    Requires: pip install openai-whisper ffmpeg-python, plus ffmpeg installed on the system.
    Model is cached after first load.
    """
    try:
        import whisper
    except ImportError as e:
        raise TranscriptionError(
            "local_whisper selected but 'openai-whisper' is not installed. "
            "Run: pip install openai-whisper"
        ) from e

    # "base" is a good speed/accuracy tradeoff; use "small"/"medium" for higher accuracy.
    model_size = os.getenv("LOCAL_WHISPER_MODEL", "base")
    model = whisper.load_model(model_size)
    result = model.transcribe(file_path)
    return result["text"]


def _transcribe_azure(file_path: str) -> str:
    """Uses Azure Cognitive Services Speech-to-Text (batch/short-audio REST call)."""
    import requests

    speech_key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    if not speech_key or not region:
        raise TranscriptionError("AZURE_SPEECH_KEY / AZURE_SPEECH_REGION not set")

    endpoint = (
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/"
        f"conversation/cognitiveservices/v1?language=en-US"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": speech_key,
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
    }
    with open(file_path, "rb") as f:
        audio_data = f.read()

    resp = requests.post(endpoint, headers=headers, data=audio_data, timeout=120)
    if resp.status_code != 200:
        raise TranscriptionError(f"Azure STT failed: {resp.status_code} {resp.text}")

    data = resp.json()
    return data.get("DisplayText", "")
