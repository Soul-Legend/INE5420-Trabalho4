import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

data = json.load(open(sys.argv[1], encoding="utf-8"))
fig, axes = plt.subplots(len(data), 1, figsize=(14, 3.2 * len(data)))
for ax, clip in zip(axes, data):
    # Project onto the vertical plane that contains the main direction of travel.
    hips = np.array([p["bones"]["Hips"][0] for p in clip["poses"]])
    d = hips[-1, :2] - hips[0, :2]
    d = d / (np.linalg.norm(d) or 1)
    for i, pose in enumerate(clip["poses"]):
        off = i * 0.9
        for name, (h, t) in pose["bones"].items():
            if "End" in name or "Thumb" in name:
                continue
            h, t = np.array(h), np.array(t)
            x = [np.dot(h[:2] - hips[i, :2], d) + off, np.dot(t[:2] - hips[i, :2], d) + off]
            color = "tab:red" if name.startswith("Left") else "tab:blue" if name.startswith("Right") else "k"
            ax.plot(x, [h[2], t[2]], color=color, lw=2)
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title(clip["label"] + "  (vermelho = lado esquerdo, azul = direito)")
    ax.set_aspect("equal")
    ax.axis("off")
plt.tight_layout()
plt.savefig(sys.argv[2], dpi=90)
