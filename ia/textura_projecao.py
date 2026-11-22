"""Step 3 of the AI character pipeline: texture atlas from the Stable Diffusion concept.

Hunyuan3D-2 generated only the shape (its texture worker is disabled on the
public Space, and Hunyuan3D-2.1 needs more GPU time than the free daily quota).
So the concept image itself becomes the texture, projected from the front:

    atlas = [ sharp concept | blurred concept ]

Front-facing faces sample the sharp half; back-facing faces sample the blurred
half, so details such as the face are not painted on the back of the head.
The white background is replaced by the colour of the nearest character pixel,
so silhouette vertices do not pick up white.

Run: uv run --no-project --with pillow --with numpy --with scipy python ia/textura_projecao.py ia/conceito/conceito_seed5420.png
Writes ia/textura/<name>_atlas.png and <name>_bbox.json (character box in the image, 0..1).
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

OUT = Path(__file__).parent / "textura"


def main(concept: str):
    OUT.mkdir(parents=True, exist_ok=True)
    image = Image.open(concept).convert("RGB")
    rgb = np.asarray(image).astype(np.float32)
    w, h = image.size
    # Background: region connected to the image border whose colour is close to
    # the border colour (the backdrop is a soft gradient, not pure white).
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    distance = np.linalg.norm(rgb - np.median(border, axis=0), axis=2)
    # The soft floor shadow under the feet (bottom quarter) is grey, low
    # saturation and light: count it as background too.
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    shadow = (saturation < 22) & (rgb.mean(axis=2) > 150)
    shadow[: int(0.75 * h)] = False
    labels, _ = ndimage.label((distance < 28) | shadow)
    edge_labels = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, edge_labels[edge_labels > 0])
    mask = ndimage.binary_opening(~background, iterations=2)
    ys, xs = np.nonzero(mask)
    bbox = dict(x0=xs.min() / w, x1=(xs.max() + 1) / w, y0=ys.min() / h, y1=(ys.max() + 1) / h)
    # Fill the background with the nearest character colour (dilation).
    _, (iy, ix) = ndimage.distance_transform_edt(~mask, return_indices=True)
    filled = rgb[iy, ix].astype(np.uint8)
    sharp = Image.fromarray(filled)
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=w / 40))
    atlas = Image.new("RGB", (2 * w, h))
    atlas.paste(sharp, (0, 0))
    atlas.paste(blurred, (w, 0))
    stem = Path(concept).stem
    atlas.save(OUT / f"{stem}_atlas.png")
    # Same image with a transparent background, as input for Hunyuan3D without
    # its own background removal (which erased the thin arms).
    alpha = ndimage.binary_dilation(mask, iterations=1)
    rgba = np.dstack([np.asarray(image), (alpha * 255).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(OUT.parent / "conceito" / f"{stem}_sem_fundo.png")
    (OUT / f"{stem}_bbox.json").write_text(json.dumps(bbox, indent=2), encoding="utf-8")
    print(bbox)


if __name__ == "__main__":
    main(sys.argv[1])
