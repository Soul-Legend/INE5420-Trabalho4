"""Step 2b: image -> textured 3D mesh with Hunyuan3D-2.1 (shape + texture).

Uses the public Hugging Face Space tencent/Hunyuan3D-2.1 (/generation_all).
Logged in ia/malha/registro.json together with the other generations.

Run: uv run --no-project --with gradio_client --with huggingface_hub python ia/gerar_malha_textura.py <image> <label>
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
SPACE = "tencent/Hunyuan3D-2.1"
PARAMS = dict(steps=30, guidance_scale=5.0, seed=1234, octree_resolution=384,
              check_box_rembg=False, num_chunks=8000, randomize_seed=False)


def as_path(value):
    if isinstance(value, dict):  # gradio "update" payload
        value = value.get("value") or value.get("path")
        if isinstance(value, dict):
            value = value.get("path")
    return value


def main(image_path: str, label: str):
    OUT.mkdir(parents=True, exist_ok=True)
    start = time.time()
    client = Client(SPACE, token=get_token())
    shape, textured, _html, stats, seed = client.predict(
        image=handle_file(image_path),
        mv_image_front=None, mv_image_back=None, mv_image_left=None, mv_image_right=None,
        api_name="/generation_all", **PARAMS,
    )
    stem = Path(image_path).stem
    files = {}
    for kind, src in (("forma", shape), ("texturizada", textured)):
        src = as_path(src)
        target = OUT / f"{stem}_{label}_{kind}{Path(src).suffix}"
        shutil.copy(src, target)
        files[kind] = target.name
    log_path = OUT / "registro.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    log.append(dict(input=Path(image_path).name, model=SPACE, params=PARAMS, seed=seed, files=files,
                    stats=stats, seconds=round(time.time() - start, 1),
                    when=datetime.now().isoformat(timespec="seconds")))
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(files)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
