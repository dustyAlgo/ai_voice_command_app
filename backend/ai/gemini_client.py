import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_PRIMARY_MODEL = "gemini-2.5-flash"
DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]


def _clean_model_name(value: object) -> str:
    model = str(value or "").strip()
    if not model:
        return ""

    model = model.strip("'\"")
    model = model.lstrip("[(").rstrip("])")
    model = model.strip("'\" ")
    model = model.rstrip(",")

    if model.startswith("models/"):
        _, _, model = model.partition("/")
        model = model.strip()

    return model


def _split_model_values(raw_models: object) -> list[str]:
    if raw_models is None:
        return []

    if isinstance(raw_models, str):
        text = raw_models.strip()
        if not text:
            return []

        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                text = text[1:-1]
            else:
                if isinstance(parsed, list):
                    return [str(value).strip() for value in parsed if str(value).strip()]

        return [value.strip() for value in text.split(",") if value.strip()]

    if isinstance(raw_models, (list, tuple, set)):
        return [str(value).strip() for value in raw_models if str(value).strip()]

    text = str(raw_models).strip()
    return [text] if text else []


def _candidate_models() -> list[str]:
    primary = _clean_model_name(getattr(settings, "GEMINI_MODEL", None)) or DEFAULT_PRIMARY_MODEL

    raw_fallbacks = getattr(settings, "GEMINI_FALLBACK_MODELS", None)
    fallback_values = _split_model_values(raw_fallbacks) or DEFAULT_FALLBACK_MODELS
    fallbacks = [model for model in (_clean_model_name(value) for value in fallback_values) if model]

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
    api_key = str(getattr(settings, "GEMINI_API_KEY", "") or "").strip().strip("'\"")
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
                message = str(exc).lower()
                if "api key was reported as leaked" in message:
                    raise RuntimeError(
                        "Gemini rejected GEMINI_API_KEY because it was reported as leaked. Generate a new key and update GEMINI_API_KEY."
                    ) from exc
                if "permission_denied" in message or "invalid_argument" in message or "unexpected model name format" in message:
                    break

    raise RuntimeError(f"Gemini failed after retries: {last_error}") from last_error
