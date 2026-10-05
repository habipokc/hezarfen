# syntax=docker/dockerfile:1
FROM python:3.14-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# GeoDjango loads GDAL/GEOS/PROJ via ctypes; gdal-bin pulls those shared libraries
# and also gives us ogr2ogr/ogrinfo/gdalwarp for the data scripts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gdal-bin curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

FROM base AS dev
# dev containers run as root on a bind mount: keep tool caches out of the source
# tree so the host user never ends up with root-owned files
ENV RUFF_CACHE_DIR=/tmp/ruff-cache
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
# source is bind-mounted over /app by docker-compose.override.yml
COPY . .
EXPOSE 8000

FROM base AS prod
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
# hashed + compressed admin assets, served by WhiteNoise (STORAGES in settings)
RUN DJANGO_DEBUG=0 python manage.py collectstatic --noinput
RUN useradd --system --uid 10001 app && chown -R app /app
USER app
EXPOSE 8000
CMD ["sh", "docker/start-web.sh"]
