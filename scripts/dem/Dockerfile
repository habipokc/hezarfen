# syntax=docker/dockerfile:1
# GDAL toolbox for `make dem`: CLI tools (gdalwarp, gdaldem, gdal2tiles) plus the Python
# bindings and numpy for the small raster steps written in Python. Debian's packages keep it
# on docker.io; nothing here runs as a service.
FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends gdal-bin python3-gdal python3-numpy curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
