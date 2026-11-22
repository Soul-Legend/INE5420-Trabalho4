"""Step 2 of the AI character pipeline: image -> 3D mesh with Hunyuan3D-2.

Uses the public Hugging Face Space tencent/Hunyuan3D-2 (shape generation).
Inputs/outputs and parameters are logged in ia/malha/registro.json.

Run: uv run --no-project --with gradio_client --with huggingface_hub python ia/gerar_malha.py ia/conceito/conceito_seed5420.png
A Hugging Face token (HF_TOKEN environment variable or `hf auth login`) gives
more GPU quota; anonymous use has a very small daily quota.
"""

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from gradio_client import Client, handle_file
from huggingface_hub import get_token

OUT = Path(__file__).parent / "malha"
SPACE = "tencent/Hunyuan3D-2"
PARAMS = dict(steps=30, guidance_scale=5.0, seed=1234, octree_resolution=256,
              check_box_rembg=True, num_chunks=8000, randomize_seed=False)


def main(image_path: str, label: str = "forma", **overrides):
    OUT.mkdir(parents=True, exist_ok=True)
    params = {**PARAMS, **overrides}
    start = time.time()
    # Token saved by `hf auth login` (never printed or stored here).
    client = Client(SPACE, token=get_token())
    # /generation_all (shape + texture) fails on the Space ("texgen_worker is not
    # defined"): its texture worker is disabled, so only the shape is generated here.
    shape, _html, stats, seed = client.predict(
        caption=None, image=handle_file(image_path),
        mv_image_front=None, mv_image_back=None, mv_image_left=None, mv_image_right=None,
        api_name="/shape_generation", **params,
    )
    if isinstance(shape, dict):  # gradio "update" payload: {"value": path, ...}
        shape = shape.get("value") or shape.get("path")
        if isinstance(shape, dict):
            shape = shape.get("path")
    stem = Path(image_path).stem
    target = OUT / f"{stem}_{label}{Path(shape).suffix}"
    shutil.copy(shape, target)
    files = {label: target.name}
    log_path = OUT / "registro.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    log.append(dict(input=Path(image_path).name, model=SPACE, params=params, seed=seed, files=files,
                    stats=stats, seconds=round(time.time() - start, 1),
                    when=datetime.now().isoformat(timespec="seconds")))
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(files, stats)


if __name__ == "__main__":
    # Optional: label key=value ... (e.g. sem_rembg check_box_rembg=0 octree_resolution=384)
    extra = {}
    for item in sys.argv[3:]:
        key, value = item.split("=")
        extra[key] = bool(int(value)) if key == "check_box_rembg" else float(value)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "forma", **extra)
