"""Step 1 of the AI character pipeline: concept images with Stable Diffusion 3.5.

Uses the public Hugging Face Space stabilityai/stable-diffusion-3.5-large-turbo
through gradio_client. Every image is saved together with its prompt, seed and
time in ia/conceito/registro.json, as evidence for the report.

Run: uv run --no-project --with gradio_client --with huggingface_hub python ia/gerar_conceito.py
"""

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

from gradio_client import Client
from huggingface_hub import get_token

OUT = Path(__file__).parent / "conceito"
SPACE = "stabilityai/stable-diffusion-3.5-large-turbo"
PROMPT = (
    "Full body 3D game character concept art of a friendly robot witch inspired by the "
    "folklore drawings of Franklin Cascaes from Santa Catarina Island, Brazil. Azorean "
    "fisherwoman shawl and short tunic made of riveted copper and ceramic plates, pointed "
    "woven straw hat, carved wooden face mask, mechanical arms and legs, boots. Standing in "
    "a symmetrical T-pose, both arms stretched straight out horizontally, legs apart and "
    "clearly separated, front view, orthographic, centered, whole body visible from hat to "
    "feet, plain white background, soft studio lighting, clean silhouette, stylized PBR"
)
NEGATIVE = (
    "multiple characters, cropped, cut off feet, side view, back view, arms down, A-pose, "
    "long skirt covering the legs, cape, scenery, background objects, text, watermark, blurry"
)
SEEDS = [11, 2026, 5420, 777]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log_path = OUT / "registro.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    client = Client(SPACE, token=get_token())
    for seed in SEEDS:
        start = time.time()
        image, used_seed = client.predict(
            prompt=PROMPT,
            negative_prompt=NEGATIVE,
            seed=seed,
            randomize_seed=False,
            width=768,
            height=1024,
            guidance_scale=0.0,
            num_inference_steps=4,
            api_name="/infer",
        )
        target = OUT / f"conceito_seed{int(used_seed)}.png"
        shutil.copy(image, target)
        entry = dict(
            file=target.name, model=SPACE, prompt=PROMPT, negative_prompt=NEGATIVE,
            seed=int(used_seed), size=[768, 1024], steps=4, guidance=0.0,
            seconds=round(time.time() - start, 1), when=datetime.now().isoformat(timespec="seconds"),
        )
        log.append(entry)
        log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
        print(entry["file"], entry["seconds"], "s")


if __name__ == "__main__":
    main()
