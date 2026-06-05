FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY migrations ./migrations

RUN python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8000
