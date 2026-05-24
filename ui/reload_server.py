#!/usr/bin/env python3
"""
Restart the local UI server when project files change.

This intentionally avoids external file-watching dependencies so `make ui-dev`
works on a fresh checkout.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WATCH_PATHS = [
    REPO_ROOT / "ui",
    REPO_ROOT / "pipeline.py",
    REPO_ROOT / "pipeline_steps",
]
IGNORE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
IGNORE_SUFFIXES = {".pyc", ".pyo", ".swp", ".tmp"}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in WATCH_PATHS:
        if path.is_file():
            files.append(path)
            continue
        if not path.exists():
            continue
        for root, dirs, names in os.walk(path):
            dirs[:] = [name for name in dirs if name not in IGNORE_DIRS]
            for name in names:
                item = Path(root) / name
                if item.suffix not in IGNORE_SUFFIXES:
                    files.append(item)
    return files


def snapshot() -> dict[str, tuple[int, int]]:
    current: dict[str, tuple[int, int]] = {}
    for path in iter_files():
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        current[str(path)] = (stat.st_mtime_ns, stat.st_size)
    return current


def start_server(host: str, port: int) -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "ui" / "pipeline_server.py"),
        "--host",
        host,
        "--port",
        str(port),
    ]
    return subprocess.Popen(cmd, cwd=REPO_ROOT, start_new_session=True)


def stop_server(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=4)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=4)


def wait_for_port(host: str, port: int, timeout: float = 4.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((host, port)) != 0:
                return
        time.sleep(0.1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-reload wrapper for the local UI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--interval", type=float, default=0.7)
    args = parser.parse_args()

    print(f"Watching UI files. Open http://{args.host}:{args.port}", flush=True)
    before = snapshot()
    proc = start_server(args.host, args.port)
    try:
        while True:
            time.sleep(args.interval)
            if proc.poll() is not None:
                print(f"Server exited with code {proc.returncode}; restarting...", flush=True)
                wait_for_port(args.host, args.port)
                proc = start_server(args.host, args.port)
                before = snapshot()
                continue

            after = snapshot()
            if after != before:
                print("Change detected; restarting UI server...", flush=True)
                stop_server(proc)
                wait_for_port(args.host, args.port)
                proc = start_server(args.host, args.port)
                before = after
    except KeyboardInterrupt:
        print("\nStopping auto-reload server...", flush=True)
        stop_server(proc)
        return 0
    finally:
        if proc.poll() is None:
            stop_server(proc)


if __name__ == "__main__":
    raise SystemExit(main())
