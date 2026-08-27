import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    aws_endpoint_url: str | None
    aws_region: str
    queue_url: str
    table_name: str


def load_settings() -> Settings:
    return Settings(
        aws_endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        queue_url=os.getenv(
            "QUEUE_URL", "http://localhost:4566/000000000000/events"
        ),
        table_name=os.getenv("TABLE_NAME", "events"),
    )
