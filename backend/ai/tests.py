from unittest.mock import patch

from django.test import SimpleTestCase
from django.test.utils import override_settings

from ai.gemini_client import _candidate_models, generate_with_retry
from ai.response_validator import ValidationError, parse_and_validate_response


class ResponseValidatorTests(SimpleTestCase):
    def test_parses_json_with_wrapping_text(self):
        raw = "Result: {\"intent\":\"add_item\",\"items\":[{\"name\":\"milk\",\"quantity\":2}],\"remove_items\":[]}"
        parsed = parse_and_validate_response(raw)
        self.assertEqual(parsed["intent"], "add_item")
        self.assertEqual(parsed["items"][0]["name"], "milk")
        self.assertEqual(parsed["items"][0]["quantity"], 2)

    def test_raises_for_missing_json(self):
        with self.assertRaises(ValidationError):
            parse_and_validate_response("not-json")

    def test_normalizes_search_size_and_prices(self):
        raw = (
            '{"intent":"search_item","search":{"name":"toothpaste","brand":"colgate","size":"100g","min_price":"2","max_price":"5"}}'
        )
        parsed = parse_and_validate_response(raw)
        self.assertEqual(parsed["search"]["size"], "100g")
        self.assertEqual(parsed["search"]["min_price"], 2.0)
        self.assertEqual(parsed["search"]["max_price"], 5.0)


class GeminiClientTests(SimpleTestCase):
    @override_settings(GEMINI_MODEL=" gemini-2.5-flash ", GEMINI_FALLBACK_MODELS="[gemini-2.5-flash,gemini-2.0-flash,gemini-2.0-flash-lite]")
    def test_candidate_models_sanitizes_bracketed_model_list(self):
        self.assertEqual(_candidate_models(), ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"])

    @override_settings(GEMINI_MODEL=None, GEMINI_FALLBACK_MODELS=None)
    def test_candidate_models_uses_defaults_when_values_missing(self):
        self.assertEqual(_candidate_models(), ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"])

    @override_settings(GEMINI_MODEL="gemini-2.5-flash", GEMINI_FALLBACK_MODELS="gemini-2.0-flash")
    @patch("ai.gemini_client.generate_structured_response")
    def test_generate_with_retry_stops_immediately_for_revoked_key(self, mock_generate):
        mock_generate.side_effect = RuntimeError(
            "403 PERMISSION_DENIED. {'error': {'message': 'Your API key was reported as leaked.'}}"
        )

        with self.assertRaises(RuntimeError) as raised:
            generate_with_retry("hello", retries=1)

        self.assertIn("GEMINI_API_KEY", str(raised.exception))
        self.assertEqual(mock_generate.call_count, 1)
