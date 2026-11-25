# syntax=docker/dockerfile:1.7
FROM cleanstart/grafana@sha256:f7d47c4ebb4b632bfb5e7d4c78b8a126e739cd6e733aeda15b720d93a4247eef AS upstream
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:28c39be5a5e1e9b85081c10740e8495f6518a865b23bc6a486637c4b21e74b43

# Keep the supported OS package inventory; never copy the vendor's unrecognized OS.
RUN apk upgrade --no-cache && apk add --no-cache tzdata \
    && mkdir -p /usr/share/grafana /var/lib/grafana /var/log/grafana /etc/grafana/provisioning \
    && chown 472:472 /var/lib/grafana /var/log/grafana
COPY --from=upstream /usr/bin/grafana /usr/bin/grafana
COPY --from=upstream /usr/share/grafana/conf /usr/share/grafana/conf
COPY --from=upstream /usr/share/grafana/public /usr/share/grafana/public
COPY --from=upstream /usr/share/grafana/data/plugins-bundled/loki /usr/share/grafana/data/plugins-bundled/loki
COPY --from=upstream /usr/share/grafana/data/plugins-bundled/prometheus /usr/share/grafana/data/plugins-bundled/prometheus
COPY --from=upstream /usr/share/grafana/data/plugins-bundled/tempo /usr/share/grafana/data/plugins-bundled/tempo

LABEL org.opsproof.grafana-source="cleanstart/grafana@sha256:f7d47c4ebb4b632bfb5e7d4c78b8a126e739cd6e733aeda15b720d93a4247eef"
# These exact bundled plugins were rebuilt by the pinned publisher. Do not allow
# arbitrary unsigned plugins or enable downloads. Their final binaries are scanned.
ENV GF_PATHS_HOME=/usr/share/grafana \
    GF_PATHS_DATA=/var/lib/grafana \
    GF_PATHS_LOGS=/var/log/grafana \
    GF_PATHS_PLUGINS=/var/lib/grafana/plugins \
    GF_PATHS_PROVISIONING=/etc/grafana/provisioning \
    GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=loki,prometheus,tempo \
    GF_PLUGINS_PREINSTALL_DISABLED=true \
    GF_ANALYTICS_REPORTING_ENABLED=false \
    GF_ANALYTICS_CHECK_FOR_UPDATES=false
WORKDIR /usr/share/grafana
USER 472:472
EXPOSE 3000
ENTRYPOINT ["/usr/bin/grafana", "server", "--homepath=/usr/share/grafana", "--config=/usr/share/grafana/conf/defaults.ini", "--packaging=docker"]
