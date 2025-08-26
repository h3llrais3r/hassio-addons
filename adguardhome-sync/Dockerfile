# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

# Setup base
ARG BUILD_ARCH
RUN case "${BUILD_ARCH}" in \
        "amd64")   YQ_ARCH="amd64" ;; \
        "aarch64") YQ_ARCH="arm64" ;; \
        "armv7")   YQ_ARCH="arm" ;; \
        "armhf")   YQ_ARCH="arm" ;; \
        "i386")    YQ_ARCH="386" ;; \
        *) echo "Unsupported yq architecture: ${BUILD_ARCH}" && exit 1 ;; \
    esac && \
    curl -L -o /tmp/yq.tar.gz \
        https://github.com/mikefarah/yq/releases/latest/download/yq_linux_${YQ_ARCH}.tar.gz && \
    mkdir -p /usr/bin && \
    tar -xzf /tmp/yq.tar.gz -C /usr/bin && \
    chmod +x /usr/bin/yq && \
    rm -rf /tmp/*

# Download and install AdGuardHome Sync
ARG ADGUARDHOME_SYNC_VERSION
RUN case "${BUILD_ARCH}" in \
        "amd64")   ADGUARDHOME_SYNC_ARCH="amd64" ;; \
        "aarch64") ADGUARDHOME_SYNC_ARCH="arm64" ;; \
        "armv7")   ADGUARDHOME_SYNC_ARCH="armv7" ;; \
        "armhf")   ADGUARDHOME_SYNC_ARCH="armv6" ;; \
        "i386")    ADGUARDHOME_SYNC_ARCH="386" ;; \
        *) echo "Unsupported adguardhome-sync architecture: ${BUILD_ARCH}" && exit 1 ;; \
    esac && \
    curl -L -o /tmp/adguardhome-sync.tar.gz \
        https://github.com/bakito/adguardhome-sync/releases/download/v${ADGUARDHOME_SYNC_VERSION}/adguardhome-sync_${ADGUARDHOME_SYNC_VERSION}_linux_${ADGUARDHOME_SYNC_ARCH}.tar.gz && \
    mkdir -p /usr/bin && \
    tar -xzf /tmp/adguardhome-sync.tar.gz -C /usr/bin && \
    chmod +x /usr/bin/adguardhome-sync && \
    rm -rf /tmp/*

# Copy root filesystem
COPY rootfs /

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -fsS http://127.0.0.1:8080/ || exit 1