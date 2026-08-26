from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError


class EventRepository:
    def __init__(self, table: Any):
        self.table = table

    def save(self, event: dict[str, Any]) -> bool:
        item = {
            **event,
            "received_at": (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            ),
            "status": "PENDING",
        }
        try:
            # This condition is the idempotency boundary: an SQS redelivery must
            # never overwrite the event that was stored by the first attempt.
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(event_id)",
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # The existing item is durable, so the duplicate can be acknowledged.
                return False
            raise
        return True
