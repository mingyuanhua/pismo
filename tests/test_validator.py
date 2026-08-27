import json

import pytest

from event_processor.validator import EventValidationError, EventValidator


@pytest.fixture
def validator():
    return EventValidator()


def event(event_type="payment.authorized"):
    payloads = {
        "payment.authorized": {
            "payment_id": "pay-123",
            "amount": 125.50,
            "currency": "USD",
        },
        "user.created": {"user_id": "user-123", "email": "test@example.com"},
    }
    return {
        "event_id": "4e2b37f2-6c9e-4dc5-a669-c3889bff23ec",
        "event_type": event_type,
        "tenant_id": "merchant-123",
        "destination": "client-a",
        "producer": "test-producer",
        "occurred_at": "2026-08-24T18:30:00Z",
        "payload": payloads[event_type],
    }


def test_valid_payment_event(validator):
    assert validator.validate(json.dumps(event()))["event_type"] == "payment.authorized"


def test_valid_user_event(validator):
    validated = validator.validate(json.dumps(event("user.created")))

    assert validated["event_type"] == "user.created"


def test_missing_envelope_field(validator):
    message = event()
    del message["tenant_id"]

    with pytest.raises(EventValidationError) as caught:
        validator.validate(json.dumps(message))

    assert caught.value.category == "invalid_envelope"


def test_unsupported_event_type(validator):
    message = event()
    message["event_type"] = "payment.refunded"

    with pytest.raises(EventValidationError) as caught:
        validator.validate(json.dumps(message))

    assert caught.value.category == "unsupported_event_type"


def test_invalid_payment_payload(validator):
    message = event()
    message["payload"]["amount"] = -1

    with pytest.raises(EventValidationError) as caught:
        validator.validate(json.dumps(message))

    assert caught.value.category == "invalid_payload"


def test_malformed_json(validator):
    for message_body in ("not-json", "NaN", "Infinity", "-Infinity"):
        with pytest.raises(EventValidationError) as caught:
            validator.validate(message_body)

        assert caught.value.category == "malformed_json"
