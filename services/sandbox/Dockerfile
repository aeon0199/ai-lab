FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY packages/policy /app/packages/policy
COPY services/sandbox /app/services/sandbox

RUN pip install --no-cache-dir -e /app/packages/policy -e /app/services/sandbox

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
