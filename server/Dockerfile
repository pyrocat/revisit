FROM python:3.12-slim as builder

SHELL ["/bin/bash", "-c"]

# GeoDjango deps
RUN apt-get update && apt-get install -y --no-install-recommends  \
    curl gdal-bin libgdal-dev binutils libproj-dev gcc libc-dev libpq-dev \
    && rm -rf  /var/cache/apt/* /var/lib/apt/lists/*

RUN useradd -Um -u 1000 --shell /bin/bash revisit_user

ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
ENV PROJ_DIR=/server

USER revisit_user
WORKDIR /server
ENV PATH="/home/revisit_user/.local/bin:$PATH"

RUN curl -sSL https://install.python-poetry.org | python3 - --version 1.8.5

FROM builder as virtualenv
SHELL ["/bin/bash", "-c"]

USER revisit_user
WORKDIR /server

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install --no-cache --without dev

FROM builder as app

SHELL ["/bin/bash", "-c"]

## creating app user
#RUN useradd -Um -u 1000 --shell /bin/bash revisit_user && \
#    apt-get update &&  \
#    apt-get install -y --no-install-recommends \
#    gdal-bin && \
#    rm -rf /var/cache/apt/* /var/lib/apt/lists/*

USER revisit_user
WORKDIR /server

ENV PATH="/home/revisit_user/.local/bin:$PATH"
ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so

# copy poetry and virtualenv
COPY --link --from=virtualenv --chown=revisit_user:revisit_user \
    /home/revisit_user/ /home/revisit_user/
COPY . .

