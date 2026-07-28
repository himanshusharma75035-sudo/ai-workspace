from __future__ import annotations

import hmac
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import ROOT_DIR, settings

SERVICE_ACTIONS = {
    "start_all": {
        "label": "Start all services",
        "confirmation": "START SERVICES",
        "impact": f"Starts project-local Ollama and the {settings.assistant_name} application if either is stopped.",
    },
    "stop_all": {
        "label": "Stop all services",
        "confirmation": "STOP SERVICES",
        "impact": f"Stops {settings.assistant_name} and Ollama. This page will become unavailable until SSH recovery.",
    },
    "restart_all": {
        "label": "Restart all services",
        "confirmation": "RESTART SERVICES",
        "impact": f"Restarts Ollama and {settings.assistant_name}, causing a short interruption.",
    },
    "restart_app": {
        "label": "Restart web application",
        "confirmation": "RESTART APP",
        "impact": f"Restarts only the {settings.assistant_name} web application.",
    },
    "start_model": {
        "label": "Start model server",
        "confirmation": "START MODEL",
        "impact": "Starts project-local Ollama without restarting the web application.",
    },
    "stop_model": {
        "label": "Stop model server",
        "confirmation": "STOP MODEL",
        "impact": f"Stops Ollama. {settings.assistant_name} remains available with controlled retrieval fallbacks.",
    },
    "restart_model": {
        "label": "Restart model server",
        "confirmation": "RESTART MODEL",
        "impact": "Restarts project-local Ollama while keeping the web application online.",
    },
}


def validate_service_request(
    action: str,
    supplied_key: str,
    confirmation: str,
    configured_key: str,
) -> dict[str, str]:
    action_details = SERVICE_ACTIONS.get(action)
    if not action_details:
        raise ValueError("Unsupported service action")
    if not hmac.compare_digest(supplied_key, configured_key):
        raise PermissionError("Service control authorisation failed")
    if confirmation.strip() != action_details["confirmation"]:
        raise ValueError(
            f'Type {action_details["confirmation"]} exactly to confirm this action'
        )
    return action_details


class ServiceController:
    def __init__(self, root: Path = ROOT_DIR):
        self.root = root.resolve()
        self.run_dir = self.root / "run"
        self.logs_dir = self.root / "logs"
        self.action_script = self.root / "scripts" / "service_action.sh"

    @property
    def supported(self) -> bool:
        return sys.platform.startswith("linux") and Path("/proc").is_dir()

    def _process_status(self, pid_name: str, expected: tuple[str, ...]) -> dict[str, Any]:
        pid_path = self.run_dir / pid_name
        result: dict[str, Any] = {
            "running": False,
            "managed": False,
            "pid": None,
            "detail": "PID file not found",
        }
        if not pid_path.is_file():
            return result
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            result["detail"] = "PID file is invalid"
            return result
        result["pid"] = pid
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            result["detail"] = "PID file is stale"
            return result
        result["running"] = True
        if not self.supported:
            result["detail"] = "Running status is only managed on the Linux RAG host"
            return result
        try:
            cwd = (Path("/proc") / str(pid) / "cwd").resolve()
            command = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except OSError:
            result["detail"] = "Process details are unavailable"
            return result
        managed = cwd == self.root and all(token in command for token in expected)
        result["managed"] = managed
        result["detail"] = "Running under project control" if managed else "PID belongs to an unmanaged process"
        return result

    def status(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "platform": sys.platform,
            "application": self._process_status("app.pid", ("uvicorn", "app.main:app")),
            "model_server": self._process_status("ollama.pid", ("ollama", "serve")),
            "recovery": {
                "status": f"cd {self.root} && ./scripts/status.sh",
                "start": f"cd {self.root} && ./scripts/start_all.sh",
                "stop": f"cd {self.root} && ./scripts/stop_all.sh",
                "restart": f"cd {self.root} && ./scripts/restart_all.sh",
            },
        }

    def schedule(self, action: str, delay_seconds: int = 2) -> int:
        if action not in SERVICE_ACTIONS:
            raise ValueError("Unsupported service action")
        if not self.supported:
            raise RuntimeError("Service controls are available only on the managed Linux RAG host")
        if not self.action_script.is_file():
            raise RuntimeError("Project service action script is missing")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.logs_dir / "service-control.log"
        log_handle = log_path.open("ab", buffering=0)
        try:
            process = subprocess.Popen(
                ["/bin/bash", str(self.action_script), action, str(delay_seconds)],
                cwd=self.root,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            log_handle.close()
        return int(process.pid)


service_controller = ServiceController()
