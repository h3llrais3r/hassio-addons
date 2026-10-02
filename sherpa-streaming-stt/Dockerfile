# Build from debian based slim image with Python 3.12 for proper compatibility with sherpa-onnx.
FROM python:3.14-slim

# keep this in sync with config.yaml version
ARG ADDON_VERSION="0.1.0"

ARG SHERPA_ONNX_VERSION="1.13.8"
ARG WYOMING_VERSION="1.10.2"
ARG ZEROCONF_VERSION="0.150.0"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_ROOT=/config/models

RUN python3 -m pip install --no-cache-dir \
        "sherpa-onnx==${SHERPA_ONNX_VERSION}" \
        "sherpa-onnx-bin==${SHERPA_ONNX_VERSION}" \
        "wyoming==${WYOMING_VERSION}" \
        "zeroconf==${ZEROCONF_VERSION}" \
        "numpy>=2.0,<3"

COPY run.sh /run.sh
COPY server.py /server.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
