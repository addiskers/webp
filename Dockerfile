# syntax=docker/dockerfile:1.6
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5008 \
    FLASK_APP=app.py

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 5008

CMD ["flask", "run", "--host=0.0.0.0", "--port=5008"]

