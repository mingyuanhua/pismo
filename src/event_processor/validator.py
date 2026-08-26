import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class EventValidationError(ValueError):
    def __init__(self, category: str, detail: str):
        self.category = category
        super().__init__(detail)


class EventValidator:
    def __init__(self, schema_dir: Path | None = None):
        schema_dir = schema_dir or Path(__file__).parents[2] / "schemas"
        self.envelope_validator = self._load_validator(
            schema_dir / "event-envelope.json"
        )
        # A schema filename is its event type, so adding a contract does not
        # require a parallel registry or another Python class.
        self.payload_validators = {
            path.stem: self._load_validator(path)
            for path in schema_dir.glob("*.json")
            if path.name != "event-envelope.json"
        }

    @staticmethod
    def _load_validator(path: Path) -> Draft202012Validator:
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, message_body: str) -> dict[str, Any]:
        try:
            # Decimal preserves JSON numbers and is accepted by DynamoDB's serializer.
            event = json.loads(message_body, parse_float=Decimal)
        except (json.JSONDecodeError, TypeError) as error:
            raise EventValidationError("malformed_json", str(error)) from error

        envelope_error = next(self.envelope_validator.iter_errors(event), None)
        if envelope_error:
            raise EventValidationError("invalid_envelope", envelope_error.message)

        event_type = event["event_type"]
        payload_validator = self.payload_validators.get(event_type)
        if payload_validator is None:
            raise EventValidationError(
                "unsupported_event_type", f"unsupported event_type: {event_type}"
            )

        payload_error = next(payload_validator.iter_errors(event["payload"]), None)
        if payload_error:
            raise EventValidationError("invalid_payload", payload_error.message)

        return event
