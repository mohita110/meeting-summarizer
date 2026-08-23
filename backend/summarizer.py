"""
LLM-based summary generation.

Given a raw meeting transcript, produces:
  - summary: short paragraph overview
  - key_decisions: list of decisions made
  - action_items: list of {task, owner, due_date} objects

Supports Anthropic (Claude), OpenAI, or Groq as the LLM provider, chosen via
the LLM_PROVIDER env var.
"""
import os
import json

SYSTEM_PROMPT = """You are an expert meeting-notes assistant. You will receive a raw transcript of a business meeting, which may come from automatic speech recognition and can contain minor errors, filler words, unclear speaker attribution, or background noise artifacts.

Your job: read past these imperfections and extract the substance of the meeting accurately, without inventing information that isn't there.

Respond ONLY with valid JSON, no markdown fences, no commentary, in exactly this shape:

{
  "summary": "<3-5 sentence overview of what the meeting was about and its outcome>",
  "key_decisions": ["<decision 1>", "<decision 2>", "..."],
  "action_items": [
    {"task": "<what needs to be done>", "owner": "<name if stated, otherwise 'Unassigned'>", "due_date": "<date if stated, otherwise 'Not specified'>"}
  ]
}

Follow these rules, especially in ambiguous or messy cases:

1. NEVER invent names, dates, or facts that are not present in the transcript. If an owner or due date isn't mentioned for a task, use "Unassigned" or "Not specified" rather than guessing.
2. If the transcript contains ASR errors, mishears, or garbled fragments, use surrounding context to infer the most likely intended meaning. Do not flag or annotate these — just extract the sense as best you can.
3. If speaker labels are missing or inconsistent, infer who is speaking from context (e.g. "as I mentioned earlier") only when it's clearly implied; otherwise attribute actions to the group or leave the owner unassigned.
4. Relative dates (e.g. "by Friday", "next week") should be captured exactly as stated in the transcript — do not convert them to specific calendar dates unless an explicit date was given.
5. If the meeting covers multiple unrelated topics, make sure the summary and lists reflect all of them, not just the first or most prominent one.
6. If there are truly no clear decisions or action items in the transcript, return empty lists for those fields rather than fabricating plausible-sounding ones.
7. Do not include side comments, small talk, or greetings in the decisions or action items — only substantive outcomes.
8. If two people appear to discuss the same task, merge it into a single action item rather than listing duplicates.
9. If the transcript is very short, partial, or too unclear to summarize meaningfully, still return valid JSON with your best-effort summary and note in the summary field that the transcript was limited, rather than leaving fields empty by default.
"""


class SummarizationError(Exception):
    pass


def summarize(transcript: str) -> dict:
    provider = os.getenv("LLM_PROVIDER", "anthropic")

    if provider == "anthropic":
        raw = _summarize_anthropic(transcript)
    elif provider == "openai":
        raw = _summarize_openai(transcript)
    elif provider == "groq":
        raw = _summarize_groq(transcript)
    else:
        raise SummarizationError(f"Unknown LLM_PROVIDER: {provider}")

    return _safe_parse_json(raw)


def _summarize_anthropic(transcript: str) -> str:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SummarizationError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Transcript:\n\n{transcript}"}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def _summarize_openai(transcript: str) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SummarizationError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript:\n\n{transcript}"},
        ],
    )
    return response.choices[0].message.content


def _summarize_groq(transcript: str) -> str:
    """
    Uses Groq's free, OpenAI-compatible chat completions endpoint.
    Sign up at console.groq.com to get a free API key.
    """
    from openai import OpenAI

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise SummarizationError("GROQ_API_KEY is not set")

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript:\n\n{transcript}"},
        ],
    )
    return response.choices[0].message.content


def _safe_parse_json(raw: str) -> dict:
    """LLMs occasionally wrap JSON in markdown fences despite instructions; strip if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise SummarizationError(f"Could not parse LLM output as JSON: {e}\nRaw output: {raw}")
