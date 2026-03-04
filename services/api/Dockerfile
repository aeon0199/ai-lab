FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY packages/domain /app/packages/domain
COPY packages/policy /app/packages/policy
COPY services/api /app/services/api

RUN pip install --no-cache-dir -e /app/packages/domain -e /app/packages/policy -e /app/services/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
