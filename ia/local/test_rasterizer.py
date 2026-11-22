"""Checks the PyTorch rasterizer against a line-by-line Python transcription of
upstream's rasterizer.cpp (CPU path) on random triangles in clip space."""

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from custom_rasterizer import MAXINT, rasterize_image  # noqa: E402


def area2(a, b, c):
    return (c[0] - a[0]) * (b[1] - a[1]) - (b[0] - a[0]) * (c[1] - a[1])


def bary(a, b, c, p):
    area = area2(a, b, c)
    if area == 0:
        return [-1.0, -1.0, -1.0]
    beta = np.float32(area2(a, p, c) / area)
    gamma = np.float32(area2(a, b, p) / area)
    return [np.float32(1.0) - beta - gamma, beta, gamma]


def reference(V, F, W, H):
    V = V.astype(np.float32)
    empty = MAXINT * MAXINT + (MAXINT - 1)
    z = np.full(H * W, empty, dtype=np.uint64)
    scr = []
    for v in V:
        scr.append([np.float32((v[0] / v[3] * 0.5 + 0.5) * (W - 1) + 0.5),
                    np.float32((0.5 + 0.5 * v[1] / v[3]) * (H - 1) + 0.5),
                    np.float32(v[2] / v[3] * 0.49999 + 0.5)])
    for i, (a, b, c) in enumerate(F):
        t = [scr[a], scr[b], scr[c]]
        xs, ys = [q[0] for q in t], [q[1] for q in t]
        for px in range(int(min(xs)), int(max(xs) + 1) + 1):
            if px < 0 or px >= W or px >= max(xs) + 1:
                continue
            for py in range(int(min(ys)), int(max(ys) + 1) + 1):
                if py < 0 or py >= H or py >= max(ys) + 1:
                    continue
                bc = bary(t[0], t[1], t[2], [np.float32(px + 0.5), np.float32(py + 0.5)])
                if all(0.0 <= x <= 1.0 for x in bc):
                    depth = bc[0] * t[0][2] + bc[1] * t[1][2] + bc[2] * t[2][2]
                    if depth < 0:
                        continue
                    token = np.uint64(int(depth * (2 << 17))) * np.uint64(MAXINT) + np.uint64(i + 1)
                    z[py * W + px] = min(z[py * W + px], token)
    f = (z % np.uint64(MAXINT)).astype(np.int64)
    f[f == MAXINT - 1] = 0
    return f.reshape(H, W)


def main():
    rng = np.random.default_rng(0)
    W, H = 64, 48
    V = np.concatenate([rng.uniform(-1.1, 1.1, (60, 2)), rng.uniform(-0.9, 0.9, (60, 1)),
                        rng.uniform(0.8, 1.2, (60, 1))], axis=1).astype(np.float32)
    F = rng.integers(0, 60, (40, 3)).astype(np.int32)
    ref = reference(V, F, W, H)
    for device in ["cpu"] + (["cuda"] if torch.cuda.is_available() else []):
        fi, bc = rasterize_image(torch.tensor(V, device=device), torch.tensor(F, device=device),
                                 torch.zeros(0), W, H)
        fi = fi.cpu().numpy()
        same = (fi == ref).mean()
        covered = fi > 0
        sums = bc.cpu().numpy()[covered].sum(axis=-1)
        print(f"{device}: identical face index on {same * 100:.2f}% of pixels; "
              f"{covered.sum()} covered; barycentric sums in [{sums.min():.5f}, {sums.max():.5f}]")


if __name__ == "__main__":
    main()
