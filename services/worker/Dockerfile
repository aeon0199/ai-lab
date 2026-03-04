FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY packages/domain /app/packages/domain
COPY packages/policy /app/packages/policy
COPY services/worker /app/services/worker

RUN pip install --no-cache-dir -e /app/packages/domain -e /app/packages/policy -e /app/services/worker

CMD ["python", "-m", "worker.main"]
