"""
ASR (Automatic Speech Recognition) integration.

Supports three interchangeable providers, selected via the ASR_PROVIDER
env var:
  - openai_whisper_api : Whisper via OpenAI's hosted API (simplest, no GPU needed)
  - local_whisper       : Whisper running locally (offline, needs openai-whisper installed)
  - azure               : Azure Cognitive Services Speech-to-Text

Swap providers without touching any other part of the app.
"""
import os


class TranscriptionError(Exception):
    pass


def transcribe(file_path: str) -> str:
    """Dispatch to the configured ASR provider and return plain transcript text."""
    provider = os.getenv("ASR_PROVIDER", "openai_whisper_api")

    if provider == "openai_whisper_api":
        return _transcribe_openai_whisper_api(file_path)
    elif provider == "groq":
        return _transcribe_groq(file_path)
    elif provider == "local_whisper":
        return _transcribe_local_whisper(file_path)
    elif provider == "azure":
        return _transcribe_azure(file_path)
    else:
        raise TranscriptionError(f"Unknown ASR_PROVIDER: {provider}")


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
