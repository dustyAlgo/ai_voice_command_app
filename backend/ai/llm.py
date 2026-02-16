from .gemini_client import generate_with_retry
from .prompt_builder import build_voice_prompt
from .response_validator import parse_and_validate_response


def parse_intent(transcript: str, context: dict | None = None) -> dict:
    context = context or {}
    prompt = build_voice_prompt(
        transcript=transcript,
        current_list=context.get("current_list", []),
        history=context.get("history", []),
        season=context.get("season", "unknown"),
        catalog_summary=context.get("catalog_summary", []),
    )
    raw = generate_with_retry(prompt, retries=1)
    return parse_and_validate_response(raw)
