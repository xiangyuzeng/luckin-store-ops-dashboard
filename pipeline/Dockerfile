# Pipeline container — runs APScheduler that collects from MySQL,
# formats data/payload.json, and pushes via GitHub Contents API.
#
# Build context expected: project root.
#   docker compose -f pipeline/docker-compose.yml up -d --build
FROM python:3.11-slim

WORKDIR /workspace

# Install deps first for layer caching.
COPY pipeline/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copy only the pipeline package; data/payload.json is regenerated on every
# scheduler tick — no need to bake the 5MB committed copy into the image.
COPY pipeline /workspace/pipeline

RUN mkdir -p /workspace/data /workspace/logs

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pipeline.scheduler.cron_runner"]
