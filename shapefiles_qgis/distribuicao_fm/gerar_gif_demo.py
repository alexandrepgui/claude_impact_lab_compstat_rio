"""
Gera um GIF animado a partir do mapa interativo `visualizacao_semanal.html`.

Estratégia:
1. Abre o HTML local em Chromium headless (Playwright).
2. Aguarda os tiles do OpenStreetMap carregarem.
3. Para cada índice de semana selecionado, chama `desenha(i)` via JS,
   espera a re-renderização e tira screenshot.
4. Empilha os frames num GIF otimizado (Pillow).

Uso:
    pip install playwright pillow
    python -m playwright install chromium
    python shapefiles_qgis/distribuicao_fm/gerar_gif_demo.py

Flags úteis:
    --step N          processa 1 a cada N semanas (default: 3)
    --width / --height tamanho do viewport (default: 960x540)
    --duration MS     duração de cada frame no GIF em ms (default: 100)
    --output PATH     caminho do GIF (default: docs/visualizacao_semanal.gif)
    --max-weeks N     limita ao máximo N semanas (debug rápido)
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = ROOT / "shapefiles_qgis" / "distribuicao_fm" / "visualizacao_semanal.html"
DEFAULT_OUTPUT = ROOT / "docs" / "visualizacao_semanal.gif"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--step", type=int, default=3, help="processa 1 a cada N semanas (default: 3)")
    p.add_argument("--width", type=int, default=960)
    p.add_argument("--height", type=int, default=540)
    p.add_argument("--duration", type=int, default=100, help="duração de cada frame no GIF (ms)")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--max-weeks", type=int, default=None, help="limita ao máximo N semanas (debug)")
    p.add_argument("--keep-frames", action="store_true", help="mantém PNGs intermediários")
    p.add_argument("--tile-wait", type=float, default=4.0, help="segundos pra esperar tiles carregarem")
    p.add_argument("--frame-wait", type=float, default=0.18, help="segundos entre desenha() e screenshot")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not HTML_PATH.exists():
        print(f"[erro] HTML não encontrado: {HTML_PATH}", file=sys.stderr)
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[erro] Playwright não instalado. Rode: pip install playwright && python -m playwright install chromium", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = Path(tempfile.mkdtemp(prefix="gif_frames_"))
    print(f"[info] frames intermediários em {frames_dir}")

    frame_paths: list[Path] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": args.width, "height": args.height})
            page = ctx.new_page()

            page.goto(HTML_PATH.as_uri())

            page.wait_for_function("typeof WEEKS !== 'undefined' && WEEKS.length > 0", timeout=30000)
            total_weeks = page.evaluate("WEEKS.length")
            print(f"[info] {total_weeks} semanas detectadas no HTML")

            print(f"[info] esperando {args.tile_wait}s pra tiles do OSM carregarem...")
            try:
                page.wait_for_load_state("networkidle", timeout=int(args.tile_wait * 1000))
            except Exception:
                pass
            time.sleep(args.tile_wait)

            indices = list(range(0, total_weeks, max(1, args.step)))
            if args.max_weeks is not None:
                indices = indices[: args.max_weeks]

            t0 = time.time()
            for n, i in enumerate(indices, start=1):
                page.evaluate(f"desenha({i})")
                time.sleep(args.frame_wait)
                fp = frames_dir / f"frame_{n:04d}.png"
                page.screenshot(path=str(fp), full_page=False)
                frame_paths.append(fp)
                if n == 1 or n % 10 == 0 or n == len(indices):
                    elapsed = time.time() - t0
                    rate = n / elapsed if elapsed else 0
                    eta = (len(indices) - n) / rate if rate else 0
                    print(f"  frame {n:>3}/{len(indices)} (semana idx={i})  {rate:.1f} fps  ETA {eta:.0f}s")

            browser.close()

        print(f"[info] montando GIF com {len(frame_paths)} frames...")
        images = [Image.open(p).convert("P", palette=Image.ADAPTIVE, colors=256) for p in frame_paths]
        if not images:
            print("[erro] nenhum frame gerado", file=sys.stderr)
            return 1

        images[0].save(
            args.output,
            save_all=True,
            append_images=images[1:],
            duration=args.duration,
            loop=0,
            optimize=True,
            disposal=2,
        )

        size_mb = args.output.stat().st_size / (1024 * 1024)
        print(f"[ok] GIF salvo: {args.output}  ({size_mb:.1f} MB, {len(frame_paths)} frames @ {args.duration}ms)")

    finally:
        if not args.keep_frames:
            shutil.rmtree(frames_dir, ignore_errors=True)
        else:
            print(f"[info] PNGs preservados em {frames_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
