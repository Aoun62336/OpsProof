"""Fetch public, regional AWS price catalogs. No AWS credentials or account APIs.

Retains source bytes/hashes and selected rows. It does not create resources,
approve spending, apply Terraform, or infer account credits/free-tier eligibility.
"""

import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.request import urlopen
from uuid import uuid4

from scripts.m5.preflight import ROOT
from scripts.m6.local_environment import utc, write_json

REGION = "ap-south-1"
SERVICES = (
    "AmazonEC2",
    "AmazonCloudWatch",
    "AmazonEKS",
    "AmazonVPC",
    "AWSDataTransfer",
)


def normalize(row):
    return {re.sub(r"[^a-z0-9]", "", key.lower()): value for key, value in row.items() if key}


def categories(row):
    value = normalize(row)
    if value.get("termtype") != "OnDemand":
        return []
    usage = value.get("usagetype", "").lower()
    family = value.get("productfamily", "").lower()
    result = []
    if (
        value.get("instancetype") == "t3.large"
        and value.get("operatingsystem") == "Linux"
        and value.get("tenancy") == "Shared"
        and value.get("preinstalledsw", "NA") == "NA"
        and value.get("capacitystatus", "Used") == "Used"
    ):
        result.append("compute_t3_large_linux")
    if value.get("volumeapiname") == "gp3" and value.get("unit") == "GB-Mo":
        result.append("ebs_gp3_storage")
    if "cpucredits:t3" in usage:
        result.append("t3_cpu_credits")
    if "datatransfer-out-bytes" in usage:
        result.append("internet_egress")
    if "datatransfer-regional-bytes" in usage:
        result.append("regional_transfer")
    if "dataprocessing-bytes" in usage and "vended" not in usage and family == "data payload":
        result.append("cloudwatch_logs_ingest")
    if usage.endswith("timedstorage-bytehrs") and value.get("unit") == "GB-Mo":
        result.append("cloudwatch_logs_storage")
    if "datascanned-bytes" in usage:
        result.append("cloudwatch_logs_query")
    if "amazoneks-hours:percluster" in usage and "extended" not in usage:
        result.append("eks_standard_control_plane")
    if "publicipv4:inuseaddress" in usage:
        result.append("public_ipv4")
    return result


def main():
    previous = sorted(
        (ROOT / ".runtime/m6/acceptance/pricing").glob("prices-*/selected-prices.json"),
        key=lambda path: path.stat().st_mtime,
    )
    cached = json.loads(previous[-1].read_text()) if previous else {}
    cache_directory = previous[-1].parent if previous else None
    output = ROOT / ".runtime/m6/acceptance/pricing" / ("prices-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "region": REGION,
        "retrieved_at": utc(),
        "sources": {},
        "selected": {},
        "credentials_used": False,
        "account_contacted": False,
    }
    for service in SERVICES:
        url = f"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{service}/current/{REGION}/index.csv"
        target = output / (service + ".csv")
        record = {"url": url, "retrieved_at": utc()}
        try:
            digest = hashlib.sha256()
            size = 0
            old = cached.get("sources", {}).get(service, {})
            cache_file = cache_directory / (service + ".csv") if cache_directory else None
            if (
                cache_file
                and cache_file.is_file()
                and old.get("url") == url
                and old.get("sha256")
                and (
                    datetime.now(UTC) - datetime.fromisoformat(old["retrieved_at"])
                ).total_seconds()
                < 86400
            ):
                with cache_file.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if actual != old["sha256"]:
                    raise ValueError("Cached pricing bytes changed")
                target = cache_file
                record = dict(old, cached_source_path=str(cache_file.relative_to(ROOT)))
                size = target.stat().st_size
            else:
                with urlopen(url, timeout=60) as response, target.open("xb") as stream:
                    if not response.url.startswith("https://pricing.us-east-1.amazonaws.com/"):
                        raise ValueError("Unexpected pricing redirect")
                    for chunk in iter(lambda: response.read(1024 * 1024), b""):
                        size += len(chunk)
                        if size > 512 * 1024 * 1024:
                            raise ValueError("Regional catalog exceeds bounded download size")
                        digest.update(chunk)
                        stream.write(chunk)
                record.update(sha256=digest.hexdigest(), bytes=size)
            with target.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                metadata = []
                for _ in range(20):
                    row = next(reader)
                    if row and row[0] == "SKU":
                        headers = row
                        break
                    metadata.append(row)
                else:
                    raise ValueError("Price catalog header not found")
                for fields in reader:
                    row = dict(zip(headers, fields, strict=True))
                    for category in categories(row):
                        report["selected"].setdefault(category, []).append(row)
                record["metadata"] = metadata
            print(service, size, "bytes; public catalog retained", flush=True)
        except Exception as exc:
            record["error_type"] = type(exc).__name__
            print(service, "BLOCKED", type(exc).__name__, flush=True)
        report["sources"][service] = record
    write_json(output / "selected-prices.json", report)
    print("Selected pricing evidence:", output / "selected-prices.json")
    return 0 if all("error_type" not in value for value in report["sources"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
