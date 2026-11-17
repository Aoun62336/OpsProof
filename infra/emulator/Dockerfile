# Linux/amd64-only local test tool, verified against AWS's detached signature.
FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal@sha256:158a9044f9dc0777f098b76c8b54346f6ed4560b9a6a416dec7a5ba3bc483af4
COPY aws-emulator.rpm /tmp/aws-emulator.rpm
RUN echo '2b2b5031e559d74c7a4154b11056be3a57716a177cd796cf058eebd91a6870d7  /tmp/aws-emulator.rpm' | sha256sum -c - \
    && rpm -i /tmp/aws-emulator.rpm && rm /tmp/aws-emulator.rpm \
    && mkdir -p /home/emulator/.aws/emulator && chown -R 1000:1000 /home/emulator \
    && printf 'emulator:x:1000:1000:Local emulator:/home/emulator:/sbin/nologin\n' >> /etc/passwd
USER 1000:1000
WORKDIR /home/emulator
ENV EMULATOR_TELEMETRY=off
EXPOSE 9297
ENTRYPOINT ["aws-emulator", "-b", "0.0.0.0", "--telemetry", "off"]
