FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY schemas schemas
COPY scripts scripts
COPY src src
COPY tests tests

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "event_processor.consumer"]
