import logging
from typing import Any

from event_processor.repository import EventRepository
from event_processor.validator import EventValidationError, EventValidator


logger = logging.getLogger(__name__)


class EventProcessor:
    def __init__(
        self,
        sqs_client: Any,
        queue_url: str,
        validator: EventValidator,
        repository: EventRepository,
    ):
        self.sqs = sqs_client
        self.queue_url = queue_url
        self.validator = validator
        self.repository = repository

    def process(self, message: dict[str, Any]) -> bool:
        try:
            event = self.validator.validate(message["Body"])
        except EventValidationError as error:
            logger.warning(
                "Event rejected: category=%s reason=%s",
                error.category,
                error,
            )
            # Leaving the message unacknowledged lets SQS retry it and apply the
            # configured redrive policy instead of silently discarding it.
            return False

        try:
            created = self.repository.save(event)
        except Exception:
            logger.exception(
                "Persistence failed: event_id=%s event_type=%s tenant_id=%s",
                event["event_id"],
                event["event_type"],
                event["tenant_id"],
            )
            return False

        if not created:
            logger.info("Duplicate event: event_id=%s", event["event_id"])

        # Delete only after DynamoDB accepts the event. SQS may redeliver
        # the message if the process exits before this point.
        self.sqs.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=message["ReceiptHandle"],
        )
        logger.info(
            "Event processed: event_id=%s event_type=%s tenant_id=%s",
            event["event_id"],
            event["event_type"],
            event["tenant_id"],
        )
        return True
