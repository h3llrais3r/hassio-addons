# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

# Setup base
ARG BUILD_ARCH
RUN case "${BUILD_ARCH}" in \
        "amd64")   YQ_ARCH="amd64" ;; \
        "aarch64") YQ_ARCH="arm64" ;; \
        *) echo "Unsupported yq architecture: ${BUILD_ARCH}" && exit 1 ;; \
    esac && \
    mkdir -p /usr/bin && \
    curl -L -o /usr/bin/yq \
        https://github.com/mikefarah/yq/releases/latest/download/yq_linux_${YQ_ARCH} && \
    chmod +x /usr/bin/yq

# Download and install AdGuardHome Sync
ARG ADGUARDHOME_SYNC_VERSION
RUN case "${BUILD_ARCH}" in \
        "amd64")   ADGUARDHOME_SYNC_ARCH="amd64" ;; \
        "aarch64") ADGUARDHOME_SYNC_ARCH="arm64" ;; \
        *) echo "Unsupported adguardhome-sync architecture: ${BUILD_ARCH}" && exit 1 ;; \
    esac && \
    mkdir -p /usr/bin && \
    curl -L -o /tmp/adguardhome-sync.tar.gz \
        https://github.com/bakito/adguardhome-sync/releases/download/v${ADGUARDHOME_SYNC_VERSION}/adguardhome-sync_${ADGUARDHOME_SYNC_VERSION}_linux_${ADGUARDHOME_SYNC_ARCH}.tar.gz && \
    tar -xzf /tmp/adguardhome-sync.tar.gz -C /usr/bin && \
    chmod +x /usr/bin/adguardhome-sync && \
    rm -rf /tmp/*

# Copy root filesystem
COPY rootfs /

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -fsS http://127.0.0.1:8080/ || exit 1