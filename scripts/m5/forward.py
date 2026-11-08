"""Own loopback-only forwards to explicitly selected local Kubernetes Services."""

import os
import socket
import subprocess
import time
from contextlib import contextmanager

from local_cluster import kubectl_prefix


@contextmanager
def services(targets):
    """Targets are (namespace, service, local_port, service_port)."""
    kube = kubectl_prefix()
    for _, _, port, _ in targets:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    processes = []
    try:
        for namespace, service, port, remote in targets:
            processes.append(
                subprocess.Popen(
                    [
                        *kube,
                        "port-forward",
                        "-n",
                        namespace,
                        "svc/" + service,
                        f"{port}:{remote}",
                        "--address",
                        "127.0.0.1",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        deadline = time.monotonic() + 30
        for _, _, port, _ in targets:
            while True:
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError("Owned port-forward exited")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Port-forward readiness timed out")
                    time.sleep(0.2)
        yield
    finally:
        for process in processes:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
