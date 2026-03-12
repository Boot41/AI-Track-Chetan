FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

# Reuse backend dependency lock because agent and backend share Python deps.
COPY server/pyproject.toml server/uv.lock /tmp/server/
RUN uv pip install --system --no-cache -r /tmp/server/pyproject.toml

COPY agent /app/agent
COPY server /app/server

EXPOSE 8001 8020

CMD ["uvicorn", "agent.app.service_api:app", "--host", "0.0.0.0", "--port", "8020"]
