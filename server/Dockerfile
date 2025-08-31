FROM python:3.12-slim

# GeoDjango deps
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev binutils libproj-dev gcc libc-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
ENV PROJ_DIR=/server

ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /server
COPY pyproject.toml /server/
COPY poetry.lock /server/

RUN poetry install  --only main --no-root --no-ansi

COPY . /app/
