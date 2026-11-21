# Match the reviewed web runtime; publish only after scan and attestation.
FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e
USER root
RUN apk upgrade --no-cache \
    && apk add --no-cache 'libxml2>=2.13.9-r3'
COPY --chown=101:101 nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 index.html /usr/share/nginx/html/index.html
USER 101:101
EXPOSE 8080
