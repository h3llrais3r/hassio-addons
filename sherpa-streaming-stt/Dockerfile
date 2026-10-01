# Build from debian based slim image with Python 3.12 for proper compatibility with sherpa-onnx.
FROM python:3.12-slim

ARG SHERPA_ONNX_VERSION="1.13.8"
ARG WYOMING_VERSION="1.10.2"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_ROOT=/config/models

RUN python3 -m pip install --no-cache-dir \
        "sherpa-onnx==${SHERPA_ONNX_VERSION}" \
        "sherpa-onnx-bin==${SHERPA_ONNX_VERSION}" \
        "wyoming==${WYOMING_VERSION}" \
        "numpy>=2.0,<3"

COPY run.sh /run.sh
COPY server.py /server.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
