from django.test import SimpleTestCase

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
