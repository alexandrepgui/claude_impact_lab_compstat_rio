#!/usr/bin/env python3
"""
Local UI server for the CompStat Rio ingestion pipeline.

It intentionally uses only the Python standard library so the hackathon demo
does not depend on a separate frontend build step or web framework.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import signal
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_ROOT = Path(__file__).resolve().parent
PIPELINE_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
PAGE_ROUTES = {"/", "/pipeline", "/auditoria", "/relatorio", "/lab"}

sys.path.insert(0, str(REPO_ROOT))
import pipeline  # noqa: E402

STEP_OUTPUTS = {
    "1": [
        "dados/df_ocorrencias_tratado - Extração 1 .csv",
        "dados/disk_denuncia.csv",
        "relints/*.docx",
    ],
    "2": [
        "shapefiles_qgis/ocorrencias/ocorrencias.shp",
        "shapefiles_qgis/disk_denuncia/disk_denuncia.shp",
        "shapefiles_qgis/fatores_urbanos/fatores_urbanos.shp",
        "shapefiles_qgis/cameras/cameras.shp",
        "shapefiles_qgis/dominio_territorial/dominio_territorial.shp",
        "shapefiles_qgis/cpsr/cpsr.shp",
    ],
    "3": [
        "relato_estruturado.jsonl",
        "review_queue.json",
    ],
    "4": [
        "shapefiles_qgis/analise/grade_risco.shp",
        "shapefiles_qgis/analise/areas_fm_risco.shp",
        "shapefiles_qgis/distribuicao_fm/zonas_semanais.shp",
        "shapefiles_qgis/distribuicao_fm/visualizacao_semanal.html",
    ],
    "5": ["score_ranking.json"],
}

STEP_HINTS = {
    "1": "Pre-check de presenca e legibilidade das fontes brutas.",
    "2": "Correcoes deterministicas e geracao das camadas canonicas.",
    "3": "Extracao semantica com LLM; sem ANTHROPIC_API_KEY cai automaticamente em stub.",
    "4": "Consolidacao v0 e motor semanal v1 para zonas dinamicas de alocacao.",
    "5": "Ranking de risco lendo zonas_semanais, com fallback para areas_fm_risco.",
}

CURRENT_RUN: dict[str, Any] | None = None
RUN_LOCK = threading.Lock()
RUN_PROCESS: subprocess.Popen[str] | None = None


def route_path(path: str) -> str:
    clean = path.split("?", 1)[0].split("#", 1)[0]
    clean = posixpath.normpath(clean)
    if not clean.startswith("/"):
        clean = f"/{clean}"
    return clean


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def step_metadata() -> list[dict[str, Any]]:
    steps = []
    for step in pipeline.STEPS:
        sid = step["id"]
        steps.append(
            {
                "id": sid,
                "name": step["name"],
                "owner": step["owner"],
                "critical": step["critical"],
                "script": str(Path(step["script"]).relative_to(REPO_ROOT)),
                "outputs": STEP_OUTPUTS.get(sid, []),
                "hint": STEP_HINTS.get(sid, ""),
            }
        )
    return steps


def pipeline_python() -> str:
    if PIPELINE_PYTHON.exists():
        return str(PIPELINE_PYTHON)
    return sys.executable


def llm_mode() -> str:
    from pipeline_steps._llm_client import is_configured

    return "sample 5" if is_configured() else "stub"


def select_steps(payload: dict[str, Any]) -> list[str]:
    all_ids = [step["id"] for step in pipeline.STEPS]
    mode = payload.get("mode", "full")
    selected = list(all_ids)

    if mode == "only":
        selected = [sid for sid in payload.get("steps", []) if sid in all_ids]
    elif mode == "from":
        from_step = str(payload.get("fromStep", "1"))
        if from_step not in all_ids:
            raise ValueError("--from invalido")
        selected = all_ids[all_ids.index(from_step) :]

    skip = {sid for sid in payload.get("skip", []) if sid in all_ids}
    selected = [sid for sid in selected if sid not in skip]
    if not selected:
        raise ValueError("Nenhum step selecionado")
    return selected


def build_args(payload: dict[str, Any], selected: list[str]) -> list[str]:
    args: list[str] = []
    mode = payload.get("mode", "full")
    if mode == "only":
        args.extend(["--only", *selected])
    elif mode == "from":
        args.extend(["--from", str(payload.get("fromStep", "1"))])

    skip = [sid for sid in payload.get("skip", []) if sid in {s["id"] for s in pipeline.STEPS}]
    if skip:
        args.extend(["--skip", *skip])
    if payload.get("dryRun"):
        args.append("--dry-run")
    return args


def new_run(payload: dict[str, Any]) -> dict[str, Any]:
    selected = select_steps(payload)
    statuses = {}
    for step in pipeline.STEPS:
        sid = step["id"]
        statuses[sid] = {
            "status": "queued" if sid in selected else "skipped",
            "startedAt": None,
            "endedAt": None,
        }

    return {
        "id": uuid.uuid4().hex[:10],
        "status": "starting",
        "createdAt": utc_now(),
        "startedAt": None,
        "endedAt": None,
        "selected": selected,
        "args": build_args(payload, selected),
        "dryRun": bool(payload.get("dryRun")),
        "steps": statuses,
        "logs": [],
        "returnCode": None,
    }


def append_log(run: dict[str, Any], line: str) -> None:
    run["logs"].append({"ts": utc_now(), "line": line.rstrip("\n")})
    run["logs"] = run["logs"][-600:]


def mark_step(run: dict[str, Any], sid: str, status: str) -> None:
    if sid not in run["steps"]:
        return
    step = run["steps"][sid]
    if status == "running" and step["startedAt"] is None:
        step["startedAt"] = utc_now()
    if status in {"success", "failed", "stopped"}:
        step["endedAt"] = utc_now()
    step["status"] = status


def parse_line(run: dict[str, Any], line: str) -> None:
    started = re.search(r"Step\s+([1-5])\s+", line)
    if started:
        mark_step(run, started.group(1), "running")

    done = re.search(r"step_([1-5])_done", line)
    if done:
        mark_step(run, done.group(1), "success")

    failed = re.search(r"step_([1-5])_failed", line)
    if failed:
        mark_step(run, failed.group(1), "failed")


def run_pipeline(run_id: str) -> None:
    global CURRENT_RUN, RUN_PROCESS

    with RUN_LOCK:
        run = CURRENT_RUN
        if not run or run["id"] != run_id:
            return
        run["status"] = "running"
        run["startedAt"] = utc_now()
        cmd = [pipeline_python(), "-u", str(REPO_ROOT / "pipeline.py"), *run["args"]]
        append_log(run, "$ " + " ".join(cmd))

    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    with RUN_LOCK:
        RUN_PROCESS = proc

    assert proc.stdout is not None
    for line in proc.stdout:
        with RUN_LOCK:
            run = CURRENT_RUN
            if not run or run["id"] != run_id:
                continue
            append_log(run, line)
            parse_line(run, line)

    return_code = proc.wait()
    with RUN_LOCK:
        run = CURRENT_RUN
        if run and run["id"] == run_id:
            run["returnCode"] = return_code
            run["endedAt"] = utc_now()
            if run["status"] == "stopping":
                run["status"] = "stopped"
                for sid in run["selected"]:
                    if run["steps"][sid]["status"] in {"queued", "running"}:
                        mark_step(run, sid, "stopped")
            elif return_code == 0:
                run["status"] = "success"
                if run["dryRun"]:
                    for sid in run["selected"]:
                        if run["steps"][sid]["status"] == "queued":
                            mark_step(run, sid, "planned")
                else:
                    for sid in run["selected"]:
                        if run["steps"][sid]["status"] in {"queued", "running"}:
                            mark_step(run, sid, "success")
            else:
                run["status"] = "failed"
                for sid in run["selected"]:
                    if run["steps"][sid]["status"] == "running":
                        mark_step(run, sid, "failed")
                    elif run["steps"][sid]["status"] == "queued":
                        run["steps"][sid]["status"] = "blocked"
            RUN_PROCESS = None


def latest_score() -> dict[str, Any] | None:
    path = REPO_ROOT / "score_ranking.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    score_field = data.get("score_field") or "risco"
    name_fields = ("nome_area", "nome_subar", "nome_zona", "nome")
    ranking = []
    for idx, row in enumerate(data.get("ranking", [])[:8], start=1):
        name = next((row.get(field) for field in name_fields if row.get(field)), "?")
        raw_score = row.get(score_field, row.get("risco", row.get("score", row.get("score_total", 0))))
        try:
            score = float(raw_score or 0)
        except (TypeError, ValueError):
            score = 0.0
        ranking.append(
            {
                "rank": idx,
                "name": str(name),
                "score": score,
                "scoreField": score_field,
                "week": row.get("semana"),
                "agents": row.get("n_agentes"),
            }
        )
    return {
        "generatedAt": data.get("generated_at"),
        "version": data.get("version"),
        "source": data.get("source_shapefile"),
        "scoreField": score_field,
        "total": data.get("n_total"),
        "ranking": ranking,
    }


def _step_from_event(event: str) -> str | None:
    match = re.match(r"(?:step_|s)([1-5])(?:_|$)", event)
    return match.group(1) if match else None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_json", "path": str(path.relative_to(REPO_ROOT))}


def count_jsonl(path: Path, limit: int = 4) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path.relative_to(REPO_ROOT)), "exists": False, "count": 0, "sample": []}

    count = 0
    sample = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            if len(sample) < limit:
                sample.append(item)
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "exists": True,
        "count": count,
        "sample": sample,
    }


def audit_summary() -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    malformed = 0
    audit_path = pipeline.AUDIT_LOG

    if audit_path.exists():
        with audit_path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                event = str(entry.get("event", "unknown"))
                level = str(entry.get("level", "INFO")).upper()
                data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
                ts = entry.get("ts")
                events.append(
                    {
                        "line": line_no,
                        "ts": ts,
                        "event": event,
                        "level": level,
                        "step": _step_from_event(event),
                        "data": data,
                    }
                )

    level_counts = {level: 0 for level in ("INFO", "OK", "WARN", "ERR")}
    step_counts = {step["id"]: {"total": 0, "ERR": 0, "WARN": 0, "OK": 0, "INFO": 0} for step in pipeline.STEPS}
    event_counts: dict[str, int] = {}
    latest_by_step: dict[str, dict[str, Any]] = {}
    runs: list[dict[str, Any]] = []
    current_run: dict[str, Any] | None = None

    for entry in events:
        level = entry["level"] if entry["level"] in level_counts else "INFO"
        level_counts[level] += 1
        event_counts[entry["event"]] = event_counts.get(entry["event"], 0) + 1

        step = entry.get("step")
        if step in step_counts:
            step_counts[step]["total"] += 1
            step_counts[step][level] += 1
            latest_by_step[step] = entry

        if entry["event"] == "pipeline_start":
            current_run = {
                "startedAt": entry.get("ts"),
                "endedAt": None,
                "status": "running",
                "steps": entry.get("data", {}).get("steps", []),
                "levels": {level_name: 0 for level_name in ("INFO", "OK", "WARN", "ERR")},
                "events": 0,
                "durationS": None,
            }
            runs.append(current_run)
        if current_run:
            current_run["events"] += 1
            current_run["levels"][level] += 1
            if entry["event"] in {"pipeline_end", "pipeline_end_with_warnings", "pipeline_aborted", "pipeline_aborted_missing_deps"}:
                current_run["endedAt"] = entry.get("ts")
                current_run["status"] = "success" if entry["event"] == "pipeline_end" else "attention"
                started = _parse_ts(current_run["startedAt"])
                ended = _parse_ts(current_run["endedAt"])
                if started and ended:
                    current_run["durationS"] = round((ended - started).total_seconds(), 1)
                current_run = None

    review_queue = read_json_file(REPO_ROOT / "review_queue.json")
    pending_items = review_queue.get("pending_items", []) if isinstance(review_queue, dict) else []
    extracted = count_jsonl(REPO_ROOT / "relato_estruturado.jsonl")

    recent = events[-80:]
    recent.reverse()
    top_events = sorted(event_counts.items(), key=lambda item: (-item[1], item[0]))[:8]

    return {
        "path": str(audit_path.relative_to(REPO_ROOT)),
        "exists": audit_path.exists(),
        "eventCount": len(events),
        "malformedCount": malformed,
        "firstTs": events[0]["ts"] if events else None,
        "lastTs": events[-1]["ts"] if events else None,
        "levelCounts": level_counts,
        "stepCounts": step_counts,
        "latestByStep": latest_by_step,
        "recentEvents": recent,
        "topEvents": [{"event": event, "count": count} for event, count in top_events],
        "runs": runs[-8:][::-1],
        "reviewQueue": {
            "path": "review_queue.json",
            "exists": (REPO_ROOT / "review_queue.json").exists(),
            "status": review_queue.get("status") if isinstance(review_queue, dict) else None,
            "generatedAt": review_queue.get("generated_at") if isinstance(review_queue, dict) else None,
            "pendingCount": len(pending_items) if isinstance(pending_items, list) else 0,
            "items": pending_items[:8] if isinstance(pending_items, list) else [],
        },
        "extractedJsonl": extracted,
    }


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        clean_path = route_path(self.path)

        if clean_path == "/api/pipeline":
            self.write_json(
                {
                    "steps": step_metadata(),
                    "requiredDeps": pipeline.REQUIRED_DEPS,
                    "llmMode": llm_mode(),
                    "pythonExecutable": pipeline_python(),
                    "auditLog": str(pipeline.AUDIT_LOG.relative_to(REPO_ROOT)),
                    "score": latest_score(),
                    "run": self.current_run(),
                }
            )
            return

        if clean_path == "/api/runs/current":
            self.write_json({"run": self.current_run()})
            return

        if clean_path == "/api/audit":
            self.write_json(audit_summary())
            return

        if clean_path in PAGE_ROUTES or (not clean_path.startswith("/api/") and Path(clean_path).suffix == ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/runs":
            payload = self.read_json()
            try:
                run = new_run(payload)
            except ValueError as exc:
                self.write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            with RUN_LOCK:
                global CURRENT_RUN
                if CURRENT_RUN and CURRENT_RUN["status"] in {"starting", "running", "stopping"}:
                    self.write_json({"error": "Ja existe uma execucao em andamento"}, HTTPStatus.CONFLICT)
                    return
                CURRENT_RUN = run

            thread = threading.Thread(target=run_pipeline, args=(run["id"],), daemon=True)
            thread.start()
            self.write_json({"run": run}, HTTPStatus.CREATED)
            return

        if self.path == "/api/runs/current/stop":
            with RUN_LOCK:
                if not CURRENT_RUN or CURRENT_RUN["status"] not in {"starting", "running"}:
                    self.write_json({"error": "Nenhuma execucao ativa"}, HTTPStatus.CONFLICT)
                    return
                CURRENT_RUN["status"] = "stopping"
                proc = RUN_PROCESS
            if proc and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
            self.write_json({"run": self.current_run()})
            return

        self.write_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def translate_path(self, path: str) -> str:
        clean = route_path(path)
        if clean in PAGE_ROUTES or (not clean.startswith("/api/") and Path(clean).suffix == ""):
            clean = "/index.html"
        return str(UI_ROOT / clean.lstrip("/"))

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def current_run() -> dict[str, Any] | None:
        with RUN_LOCK:
            return json.loads(json.dumps(CURRENT_RUN, ensure_ascii=False)) if CURRENT_RUN else None


def main() -> int:
    parser = argparse.ArgumentParser(description="CompStat Rio pipeline UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ReusableThreadingHTTPServer((args.host, args.port), Handler)
    host, port = server.server_address[:2]
    print(f"Pipeline UI: http://{host}:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping server...")
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
