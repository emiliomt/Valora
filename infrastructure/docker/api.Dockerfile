FROM python:3.11-slim

WORKDIR /srv

COPY services/financial-engine /srv/services/financial-engine
COPY apps/api /srv/apps/api

RUN pip install --no-cache-dir -e /srv/services/financial-engine -e /srv/apps/api

WORKDIR /srv/apps/api
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
