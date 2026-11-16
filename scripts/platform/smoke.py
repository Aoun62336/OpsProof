"""Own both local port forwards so smoke cannot silently hit Compose."""

import os
import socket
import subprocess
import time
from contextlib import contextmanager

from local_cluster import kubectl_prefix
from preflight import ROOT
from verify_k3d import verify


@contextmanager
def forwarded_apis():
    kube = kubectl_prefix()
    ports = [("demo", 18088), ("control", 18090)]
    for _, port in ports:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    processes = []
    try:
        for component, port in ports:
            processes.append(
                subprocess.Popen(
                    [
                        *kube,
                        "port-forward",
                        "-n",
                        f"opsproof-{component}",
                        f"svc/{component}-api",
                        f"{port}:8080",
                        "--address",
                        "127.0.0.1",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        deadline = time.monotonic() + 30
        for _, port in ports:
            while True:
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError("Owned Kubernetes port-forward exited")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Kubernetes forwarding deadline exceeded") from None
                    time.sleep(0.2)
        yield
    finally:
        for process in processes:
            if os.name == "nt":
                # Chocolatey wrappers spawn kubectl children; stop the owned tree.
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


def main():
    with forwarded_apis():
        verify(ROOT / ".env")


if __name__ == "__main__":
    main()
