FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run uses PORT env var
ENV PORT=8080

# Run with gunicorn for production. --timeout is high enough to cover the
# synchronous server-creation walk served by /internal/create (Cloud Tasks
# target); it must stay >= the Cloud Run service timeout_seconds.
CMD exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 900 main:app
