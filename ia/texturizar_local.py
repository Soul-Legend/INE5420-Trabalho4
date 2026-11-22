"""Step 3b: texture the Hunyuan3D-2 shape LOCALLY with Hunyuan3D-Paint (AMD GPU).

Runs Tencent's official Hunyuan3D-2 texture pipeline (delight + multiview
paint "turbo" + back-projection bake) on this computer's Radeon RX 9070 XT,
with the official AMD ROCm build of PyTorch for Windows.

Two adaptations, both outside Tencent's code:
- `custom_rasterizer` (a CUDA/C++ extension that cannot be built for Windows
  ROCm) is replaced by a pure-PyTorch implementation with the same interface,
  verified pixel by pixel against a transcription of the original C++
  (D:/Programs/hy3d/compat).
- "cuda" in the code maps to the ROCm device; HIP_VISIBLE_DEVICES=1 hides the
  integrated GPU, and TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1 enables flash
  attention (checked against exact attention before use).

Run (from Trabalho4):
  D:/Programs/hy3d/.venv/Scripts/python.exe ia/texturizar_local.py <shape.glb> <image.png> <out.glb>
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HY3D = Path("D:/Programs/hy3d")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
os.environ.setdefault("HF_HOME", str(HY3D / "hf"))
sys.path.insert(0, str(HY3D / "compat"))  # pure-PyTorch custom_rasterizer
sys.path.insert(1, str(HY3D / "Hunyuan3D-2"))

import torch  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image  # noqa: E402

from hy3dgen.shapegen.postprocessors import DegenerateFaceRemover, FaceReducer, FloaterRemover  # noqa: E402
from hy3dgen.texgen import Hunyuan3DPaintPipeline  # noqa: E402


def main(shape_path, image_path, out_path):
    start = time.time()
    print("GPU:", torch.cuda.get_device_name(0))
    mesh = trimesh.load(shape_path, force="mesh")
    faces_in = len(mesh.faces)
    # Same clean-up as Tencent's demo before painting.
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    mesh = FaceReducer()(mesh, max_facenum=40000)
    print(f"faces: {faces_in} -> {len(mesh.faces)}")

    pipeline = Hunyuan3DPaintPipeline.from_pretrained("tencent/Hunyuan3D-2", subfolder="hunyuan3d-paint-v2-0-turbo")
    loaded = time.time()
    image = Image.open(image_path)
    textured = pipeline(mesh, image=image)
    textured.export(out_path)
    done = time.time()

    log_path = Path(__file__).parent / "malha" / "registro.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    log.append(dict(
        input_shape=Path(shape_path).name, input_image=Path(image_path).name,
        model="tencent/Hunyuan3D-2 (hunyuan3d-delight-v2-0 + hunyuan3d-paint-v2-0-turbo), local",
        device=torch.cuda.get_device_name(0), torch=torch.__version__,
        faces=[faces_in, len(mesh.faces)], output=Path(out_path).name,
        seconds_load=round(loaded - start, 1), seconds_paint=round(done - loaded, 1),
        peak_gpu_gib=round(torch.cuda.max_memory_allocated() / 2**30, 2),
        when=datetime.now().isoformat(timespec="seconds"),
    ))
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"done: load {loaded - start:.0f}s, paint {done - loaded:.0f}s, "
          f"peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB -> {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
