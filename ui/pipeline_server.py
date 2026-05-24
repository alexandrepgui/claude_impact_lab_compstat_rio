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
CONFIG_PESOS = REPO_ROOT / "shapefiles_qgis" / "config_pesos.json"
MOTOR_SCRIPT = REPO_ROOT / "shapefiles_qgis" / "motor_bingo_semanal.py"
SCORE_JSON = REPO_ROOT / "score_ranking.json"
SCORE_JSON_SNAPSHOT = REPO_ROOT / "score_ranking.previous.json"

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
        "llmSample": payload.get("llmSample"),
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

    run_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    llm_sample = run.get("llmSample") if run else None
    if llm_sample:
        run_env["PIPELINE_LLM_SAMPLE"] = str(llm_sample)

    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=run_env,
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


def _score_payload(path: Path, limit: int = 8) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    score_field = data.get("score_field") or "risco"
    name_fields = ("nome_area", "nome_subar", "nome_zona", "nome")
    ranking = []
    for idx, row in enumerate(data.get("ranking", [])[:limit], start=1):
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


def latest_score() -> dict[str, Any] | None:
    return _score_payload(SCORE_JSON)


def lab_load_config() -> dict[str, Any]:
    if not CONFIG_PESOS.exists():
        raise FileNotFoundError(f"config_pesos.json not found at {CONFIG_PESOS}")
    return json.loads(CONFIG_PESOS.read_text(encoding="utf-8"))


def lab_save_config(new_cfg: dict[str, Any]) -> dict[str, Any]:
    # Minimal structural validation — keep the same top-level keys + at least one layer.
    if not isinstance(new_cfg, dict):
        raise ValueError("config deve ser objeto JSON")
    if "camadas" not in new_cfg or not isinstance(new_cfg["camadas"], dict):
        raise ValueError("config.camadas ausente ou invalido")
    for name, cam in new_cfg["camadas"].items():
        if not isinstance(cam, dict):
            raise ValueError(f"camada {name} deve ser objeto")
        if "peso" in cam:
            try:
                cam["peso"] = float(cam["peso"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"camada {name}.peso invalido: {cam['peso']}") from exc
        if "peso_categoria_default" in cam:
            try:
                cam["peso_categoria_default"] = float(cam["peso_categoria_default"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"camada {name}.peso_categoria_default invalido") from exc
        if "ativa" in cam:
            cam["ativa"] = bool(cam["ativa"])
        if "pesos_categoria" in cam:
            if not isinstance(cam["pesos_categoria"], dict):
                raise ValueError(f"camada {name}.pesos_categoria deve ser objeto")
            for catkey, catval in list(cam["pesos_categoria"].items()):
                try:
                    cam["pesos_categoria"][catkey] = float(catval)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"camada {name}.pesos_categoria[{catkey}] invalido"
                    ) from exc
    for key in ("janela_semanas", "grade_m", "n_agentes"):
        if key in new_cfg:
            try:
                new_cfg[key] = int(new_cfg[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} deve ser inteiro") from exc
    for key in ("cobertura", "min_share_zona"):
        if key in new_cfg:
            try:
                new_cfg[key] = float(new_cfg[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} deve ser numero") from exc

    CONFIG_PESOS.write_text(
        json.dumps(new_cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return new_cfg


def snapshot_previous_ranking() -> None:
    if SCORE_JSON.exists():
        SCORE_JSON_SNAPSHOT.write_text(
            SCORE_JSON.read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def new_lab_run() -> dict[str, Any]:
    # Lab rescore = motor_bingo_semanal.py (v1) + pipeline.py --only 5
    return {
        "id": uuid.uuid4().hex[:10],
        "kind": "lab_rescore",
        "status": "starting",
        "createdAt": utc_now(),
        "startedAt": None,
        "endedAt": None,
        "selected": ["motor_v1", "5"],
        "args": [],
        "dryRun": False,
        "llmSample": None,
        "steps": {
            "motor_v1": {"status": "queued", "startedAt": None, "endedAt": None},
            "5": {"status": "queued", "startedAt": None, "endedAt": None},
        },
        "logs": [],
        "returnCode": None,
    }


def run_lab_rescore(run_id: str) -> None:
    global CURRENT_RUN, RUN_PROCESS

    with RUN_LOCK:
        run = CURRENT_RUN
        if not run or run["id"] != run_id:
            return
        run["status"] = "running"
        run["startedAt"] = utc_now()

    py = pipeline_python()
    commands = [
        ("motor_v1", [py, "-u", str(MOTOR_SCRIPT)], MOTOR_SCRIPT.parent),
        ("5", [py, "-u", str(REPO_ROOT / "pipeline.py"), "--only", "5"], REPO_ROOT),
    ]

    run_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    overall_rc = 0

    for sid, cmd, cwd in commands:
        with RUN_LOCK:
            run = CURRENT_RUN
            if not run or run["id"] != run_id:
                return
            if run["status"] == "stopping":
                mark_step(run, sid, "stopped")
                continue
            append_log(run, "$ " + " ".join(cmd))
            mark_step(run, sid, "running")

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=run_env,
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
                # Reuse pipeline.py parser for step 5 markers
                parse_line(run, line)

        rc = proc.wait()
        with RUN_LOCK:
            run = CURRENT_RUN
            if not run or run["id"] != run_id:
                return
            if run["status"] == "stopping":
                mark_step(run, sid, "stopped")
                overall_rc = 130
                break
            if rc != 0:
                mark_step(run, sid, "failed")
                overall_rc = rc
                break
            else:
                # parse_line may already have set s5 to success via marker;
                # otherwise force it.
                if run["steps"][sid]["status"] != "success":
                    mark_step(run, sid, "success")

    with RUN_LOCK:
        run = CURRENT_RUN
        if run and run["id"] == run_id:
            run["returnCode"] = overall_rc
            run["endedAt"] = utc_now()
            if run["status"] == "stopping":
                run["status"] = "stopped"
            elif overall_rc == 0:
                run["status"] = "success"
            else:
                run["status"] = "failed"
            RUN_PROCESS = None


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/pipeline":
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

        if self.path == "/api/runs/current":
            self.write_json({"run": self.current_run()})
            return

        if self.path == "/api/lab/config":
            try:
                cfg = lab_load_config()
            except FileNotFoundError as exc:
                self.write_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                return
            self.write_json(
                {
                    "config": cfg,
                    "path": str(CONFIG_PESOS.relative_to(REPO_ROOT)),
                }
            )
            return

        if self.path == "/api/lab/snapshot":
            self.write_json(
                {
                    "current": _score_payload(SCORE_JSON),
                    "previous": _score_payload(SCORE_JSON_SNAPSHOT),
                }
            )
            return

        if self.path == "/":
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

        if self.path == "/api/lab/config":
            payload = self.read_json()
            new_cfg = payload.get("config") if isinstance(payload, dict) else None
            if new_cfg is None:
                self.write_json({"error": "config ausente"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                saved = lab_save_config(new_cfg)
            except ValueError as exc:
                self.write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.write_json({"config": saved})
            return

        if self.path == "/api/lab/rerun":
            with RUN_LOCK:
                global CURRENT_RUN
                if CURRENT_RUN and CURRENT_RUN["status"] in {"starting", "running", "stopping"}:
                    self.write_json(
                        {"error": "Ja existe uma execucao em andamento"},
                        HTTPStatus.CONFLICT,
                    )
                    return
                snapshot_previous_ranking()
                CURRENT_RUN = new_lab_run()
                run = CURRENT_RUN
            thread = threading.Thread(target=run_lab_rescore, args=(run["id"],), daemon=True)
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
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean == "/":
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

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Pipeline UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping server...")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
