# syntax=docker/dockerfile:1
FROM python:3.13-slim AS build
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# The wheels are mounted only for this step, so they stay out of the image layers.
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    apt-get update && apt-get install --no-install-recommends -y smartmontools ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir /wheels/*.whl \
    && groupadd --gid 10001 telemetry && useradd --uid 10001 --gid 10001 --no-create-home telemetry \
    && install -d -o 10001 -g 10001 -m 0755 /data \
    && install -d -o 10001 -g 10001 -m 0700 /secrets \
    && install -d -o 0 -g 0 -m 0755 /snapshots /opt/ugreen
COPY host-smart-snapshot.py /opt/ugreen/host-smart-snapshot.py
USER 10001:10001
ENTRYPOINT ["ugreen-telemetry"]
