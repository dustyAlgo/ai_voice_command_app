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

    def test_normalizes_search_size_and_prices(self):
        raw = (
            '{"intent":"search_item","search":{"name":"toothpaste","brand":"colgate","size":"100g","min_price":"2","max_price":"5"}}'
        )
        parsed = parse_and_validate_response(raw)
        self.assertEqual(parsed["search"]["size"], "100g")
        self.assertEqual(parsed["search"]["min_price"], 2.0)
        self.assertEqual(parsed["search"]["max_price"], 5.0)
