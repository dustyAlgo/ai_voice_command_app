import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _candidate_models() -> list[str]:
    primary = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    raw_fallbacks = getattr(
        settings,
        "GEMINI_FALLBACK_MODELS",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
    )
    if isinstance(raw_fallbacks, str):
        fallbacks = [value.strip() for value in raw_fallbacks.split(",") if value.strip()]
    else:
        fallbacks = [str(value).strip() for value in raw_fallbacks if str(value).strip()]

    ordered = [primary] + fallbacks
    deduped = []
    seen = set()
    for model in ordered:
        if model in seen:
            continue
        seen.add(model)
        deduped.append(model)
    return deduped


def generate_structured_response(prompt: str, model_name: str) -> str:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("google-genai package is not installed.") from exc

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={"temperature": 0.2, "max_output_tokens": 1200},
    )

    if not response or not getattr(response, "text", ""):
        raise ValueError("Gemini returned an empty response.")

    return response.text


def generate_with_retry(prompt: str, retries: int = 1) -> str:
    models = _candidate_models()
    last_error = None

    for model_name in models:
        for _ in range(retries + 1):
            try:
                return generate_structured_response(prompt, model_name=model_name)
            except Exception as exc:  # pragma: no cover
                last_error = exc
                logger.warning("Gemini call failed for model %s: %s", model_name, exc)

    raise RuntimeError(f"Gemini failed after retries: {last_error}") from last_error
