"""Supervisor for the independent, read-only observation process."""

import json
import os
import subprocess
import sys
import time

from scripts.m6.local_environment import ROOT, write_json


def child_environment(access):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AWS_", "GROQ_", "GEMINI_", "OPSPROOF_"))
    }
    return {**env, **access.environment("observe")}


class LiveObserver:
    def __init__(self, directory, access, state):
        self.directory = directory
        self.env = child_environment(access)
        write_json(
            directory / "observer-request.json",
            {
                "trial_id": state["trial_id"],
                "scenario": state["scenario"],
                "target_uid": state["target_uid"],
            },
        )
        self.log = (directory / "observer-process.log").open("x", encoding="utf-8")
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.m6.observe_local_trial",
                "--run-directory",
                str(directory),
            ],
            cwd=ROOT,
            env=self.env,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        deadline = time.monotonic() + 30
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError("Independent observer exited before dispatch")
                identity = directory / "observer/identity.json"
                if identity.exists():
                    self.identity = json.loads(identity.read_text(encoding="utf-8"))
                    return
                time.sleep(0.1)
            raise TimeoutError("Independent observer not ready before dispatch")
        except BaseException:
            self.stop()
            raise

    def stop(self):
        marker = self.directory / "observer-stop"
        if not marker.exists():
            marker.write_text("stop\n", encoding="utf-8")
        if self.process.poll() is None:
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        self.log.close()
