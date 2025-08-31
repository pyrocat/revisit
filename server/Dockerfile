FROM python:3.12-slim as builder

SHELL ["/bin/bash", "-c"]

# GeoDjango deps
RUN apt-get update && apt-get install -y --no-install-recommends  \
    curl gdal-bin libgdal-dev binutils libproj-dev gcc libc-dev libpq-dev \
    && rm -rf  /var/cache/apt/* /var/lib/apt/lists/*

RUN useradd -Um -u 1000 --shell /bin/bash revisit_user

ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
ENV PROJ_DIR=/server

ENV PATH="~/.local/bin:$PATH"

WORKDIR /server

RUN curl -sSL https://install.python-poetry.org | python3 - --version 1.8.5

FROM builder as virtualenv

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install --no-cache

FROM python:3.12-slim as app

SHELL ["/bin/bash", "-c"]

# creating app user
RUN useradd -Um -u 1000 --shell /bin/bash revisit_user && \
    apt-get update &&  \
    apt-get install -y --no-install-recommends \
    gdal-bin && \
    rm -rf /var/cache/apt/* /var/lib/apt/lists/* \

USER revisit_user

ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
COPY . .

# copy poetry and virtualenv
COPY --link --from=virtualenv --chown=helpdeskapi:helpdeskapi \
    /home/revisit_user/ /home/revisit_user/
COPY --link --from=virtualenv --chown=helpdeskapi:helpdeskapi \
    /server/ /server/


WORKDIR /server

