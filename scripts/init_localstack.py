import os

import boto3
from botocore.exceptions import ClientError


ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")
QUEUE_NAME = os.getenv("QUEUE_NAME", "events")
DLQ_NAME = os.getenv("DLQ_NAME", "events-dlq")
TABLE_NAME = os.getenv("TABLE_NAME", "events")


def create_queues() -> None:
    sqs = boto3.client("sqs", endpoint_url=ENDPOINT_URL, region_name=REGION)
    # The main queue's redrive policy needs the DLQ ARN, so create the DLQ first.
    dlq_url = sqs.create_queue(QueueName=DLQ_NAME)["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]

    sqs.create_queue(
        QueueName=QUEUE_NAME,
        Attributes={
            "VisibilityTimeout": "10",
            "RedrivePolicy": (
                f'{{"deadLetterTargetArn":"{dlq_arn}","maxReceiveCount":"3"}}'
            ),
        },
    )


def create_table() -> None:
    dynamodb = boto3.client("dynamodb", endpoint_url=ENDPOINT_URL, region_name=REGION)
    try:
        dynamodb.create_table(
            TableName=TABLE_NAME,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "event_id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "received_at", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-received_at-index",
                    # The future Sender can query pending work oldest-first
                    # without scanning the table.
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "received_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
    except ClientError as error:
        # Compose may run the initializer again against an existing LocalStack.
        if error.response["Error"]["Code"] != "ResourceInUseException":
            raise


if __name__ == "__main__":
    create_queues()
    create_table()
    print(f"Created queues {QUEUE_NAME}/{DLQ_NAME} and table {TABLE_NAME}")
