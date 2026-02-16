import json


def build_voice_prompt(*, transcript, current_list, history, season, catalog_summary):
    schema = {
        "intent": "add_item | remove_item | search_item | modify_item | mixed | unknown",
        "language": "en | hi",
        "items": [{"name": "string", "quantity": 1}],
        "remove_items": ["string"],
        "modify_items": [{"name": "string", "quantity": 1}],
        "search": {
            "name": "string or null",
            "brand": "string or null",
            "size": "string or null",
            "min_price": 0,
            "max_price": 0,
        },
        "suggestions": [{"item": "string", "reason": "string"}],
        "substitutes": [{"original": "string", "alternative": "string", "reason": "string"}],
    }

    instruction = """
You are an AI shopping assistant.
Return ONLY valid JSON.
No markdown and no extra commentary.
Support English and Hindi user commands.
Extract intent(s), entities, quantities, remove commands, and search filters (name, brand, size, min/max price).
If multiple actions are present, set intent to mixed.
""".strip()

    payload = {
        "transcript": transcript,
        "current_list": current_list,
        "recent_history": history,
        "current_season": season,
        "catalog_summary": catalog_summary,
        "expected_output_schema": schema,
    }

    return f"{instruction}\n\nINPUT:\n{json.dumps(payload, ensure_ascii=False)}"
