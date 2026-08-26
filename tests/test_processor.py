import json
from unittest.mock import Mock

from botocore.exceptions import ClientError

from event_processor.processor import EventProcessor
from event_processor.repository import EventRepository
from event_processor.validator import EventValidator


QUEUE_URL = "http://sqs.test/events"


def event():
    return {
        "event_id": "4e2b37f2-6c9e-4dc5-a669-c3889bff23ec",
        "event_type": "payment.authorized",
        "tenant_id": "merchant-123",
        "destination": "client-a",
        "producer": "test-producer",
        "occurred_at": "2026-08-24T18:30:00Z",
        "payload": {"payment_id": "pay-123", "amount": 10, "currency": "USD"},
    }


def message(body=None):
    return {"Body": body or json.dumps(event()), "ReceiptHandle": "receipt-1"}


def processor(repository=None, sqs=None):
    return EventProcessor(
        sqs_client=sqs or Mock(),
        queue_url=QUEUE_URL,
        validator=EventValidator(),
        repository=repository or Mock(save=Mock(return_value=True)),
    )


def test_valid_event_is_persisted_and_acknowledged():
    repository = Mock(save=Mock(return_value=True))
    sqs = Mock()
    worker = processor(repository, sqs)

    assert worker.process(message()) is True

    repository.save.assert_called_once()
    sqs.delete_message.assert_called_once_with(
        QueueUrl=QUEUE_URL, ReceiptHandle="receipt-1"
    )


def test_persistence_happens_before_acknowledgement():
    calls = []
    repository = Mock()
    repository.save.side_effect = lambda _: calls.append("save") or True
    sqs = Mock()
    sqs.delete_message.side_effect = lambda **_: calls.append("delete")

    processor(repository, sqs).process(message())

    assert calls == ["save", "delete"]


def test_persistence_failure_does_not_acknowledge():
    repository = Mock()
    repository.save.side_effect = RuntimeError("DynamoDB unavailable")
    sqs = Mock()

    assert processor(repository, sqs).process(message()) is False
    sqs.delete_message.assert_not_called()


def test_duplicate_event_is_acknowledged():
    repository = Mock(save=Mock(return_value=False))
    sqs = Mock()

    assert processor(repository, sqs).process(message()) is True
    sqs.delete_message.assert_called_once()


def test_invalid_event_is_not_persisted_or_acknowledged():
    repository = Mock()
    sqs = Mock()

    assert processor(repository, sqs).process(message("not-json")) is False
    repository.save.assert_not_called()
    sqs.delete_message.assert_not_called()


def test_repository_writes_conditionally_and_reports_duplicates():
    table = Mock()
    repository = EventRepository(table)

    assert repository.save(event()) is True

    item = table.put_item.call_args.kwargs["Item"]
    assert item["status"] == "PENDING"
    assert item["received_at"].endswith("Z")
    assert table.put_item.call_args.kwargs["ConditionExpression"] == (
        "attribute_not_exists(event_id)"
    )
    table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
        "PutItem",
    )

    assert repository.save(event()) is False
