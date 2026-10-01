# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

ARG SHERPA_ONNX_VERSION
ARG WYOMING_VERSION

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_ROOT=/config/models

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install \
        "sherpa-onnx==${SHERPA_ONNX_VERSION}" \
        "wyoming==${WYOMING_VERSION}" \
        "numpy>=2.0,<3" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:${PATH}"

COPY run.sh /run.sh
COPY server.py /server.py
RUN chmod +x /run.sh

CMD ["/run.sh"]
