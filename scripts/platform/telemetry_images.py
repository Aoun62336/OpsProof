"""External telemetry pins and the separately built, source-identified Grafana artifact."""

import json

from scripts.platform.preflight import ROOT
from scripts.reliability.build_images_local import context_hash


def external_images():
    return json.loads((ROOT / "observability/images.lock.json").read_text(encoding="utf-8"))


def local_grafana_image():
    return "opsproof-grafana:src-" + context_hash(ROOT / "observability/grafana")[:16]


def runtime_images(grafana_image=None):
    return {**external_images(), "grafana": grafana_image or local_grafana_image()}
