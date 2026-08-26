import argparse
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import boto3


def make_event(event_type: str) -> dict:
    payloads = {
        "payment.authorized": {
            "payment_id": f"pay-{uuid4().hex[:8]}",
            "amount": 125.50,
            "currency": "USD",
        },
        "user.created": {
            "user_id": f"user-{uuid4().hex[:8]}",
            "email": "test@example.com",
        },
        "invalid": {
            "payment_id": "pay-invalid",
            "amount": -1,
            "currency": "USD",
        },
    }
    return {
        "event_id": str(uuid4()),
        # Keep a supported type for the invalid example so it exercises payload
        # validation and the normal SQS-to-DLQ retry path.
        "event_type": (
            "payment.authorized" if event_type == "invalid" else event_type
        ),
        "tenant_id": "merchant-123",
        "destination": "client-a",
        "producer": "sample-producer",
        "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payloads[event_type],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a sample event to SQS")
    parser.add_argument(
        "event_type",
        choices=["payment.authorized", "user.created", "invalid"],
    )
    args = parser.parse_args()

    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    queue_url = os.getenv(
        "QUEUE_URL", "http://localhost:4566/000000000000/events"
    )
    sqs = boto3.client(
        "sqs",
        endpoint_url=endpoint_url,
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    event = make_event(args.event_type)
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(event))
    print(f"Sent {event['event_type']} event {event['event_id']}")
