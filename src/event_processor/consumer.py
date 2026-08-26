import logging

import boto3

from event_processor.config import load_settings
from event_processor.processor import EventProcessor
from event_processor.repository import EventRepository
from event_processor.validator import EventValidator


logger = logging.getLogger(__name__)


def build_processor() -> EventProcessor:
    settings = load_settings()
    session = boto3.session.Session(region_name=settings.aws_region)
    sqs = session.client("sqs", endpoint_url=settings.aws_endpoint_url)
    dynamodb = session.resource("dynamodb", endpoint_url=settings.aws_endpoint_url)
    return EventProcessor(
        sqs_client=sqs,
        queue_url=settings.queue_url,
        validator=EventValidator(),
        repository=EventRepository(dynamodb.Table(settings.table_name)),
    )


def run_forever() -> None:
    processor = build_processor()
    logger.info("Event processor started")

    while True:
        # Long polling avoids a tight loop and reduces empty SQS receives.
        response = processor.sqs.receive_message(
            QueueUrl=processor.queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,
        )
        for message in response.get("Messages", []):
            try:
                processor.process(message)
            except Exception:
                logger.exception("Unexpected error while processing SQS message")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_forever()
