"""Inspect motion-capture FBX files with Blender (run: blender -b -P inspect_mocap.py -- <dir> <out.json>)."""
import json
import math
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1 :]
folder, out_path = Path(args[0]), Path(args[1])
report = []

for fbx in sorted(folder.glob("*.fbx")):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True)
    scene = bpy.context.scene
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    meshes = [o.name for o in scene.objects if o.type == "MESH"]
    entry = dict(
        file=fbx.name,
        fps=scene.render.fps / scene.render.fps_base,
        armatures=[],
        meshes=meshes,
        other=[f"{o.name}:{o.type}" for o in scene.objects if o.type not in ("ARMATURE", "MESH")][:10],
    )
    for arm in arms:
        action = arm.animation_data.action if arm.animation_data else None
        start, end = (int(action.frame_range[0]), int(action.frame_range[1])) if action else (0, 0)
        roots = [b.name for b in arm.data.bones if b.parent is None]
        root = arm.pose.bones[roots[0]] if roots else None
        # Find hips-like bone: first bone with 'hip' in its name, else root.
        hips_name = next((b.name for b in arm.data.bones if "hip" in b.name.lower()), roots[0] if roots else None)
        hips = arm.pose.bones.get(hips_name) if hips_name else None
        samples = []
        step = max(1, int(entry["fps"] // 10))
        for f in range(start, end + 1, step):
            scene.frame_set(f)
            if hips:
                p = arm.matrix_world @ hips.head
                samples.append((f, p.x, p.y, p.z))
        speeds = []
        for (f0, x0, y0, _), (f1, x1, y1, _) in zip(samples, samples[1:]):
            dt = (f1 - f0) / entry["fps"]
            speeds.append(math.hypot(x1 - x0, y1 - y0) / dt)
        # Smoothed speed over 1 s windows to classify segments.
        window = 10
        smooth = [sum(speeds[i:i + window]) / len(speeds[i:i + window]) for i in range(0, len(speeds), window)]
        entry["armatures"].append(
            dict(
                name=arm.name,
                bones=len(arm.data.bones),
                bone_names=[b.name for b in arm.data.bones][:60],
                roots=roots,
                hips=hips_name,
                action=action.name if action else None,
                frames=[start, end],
                seconds=round((end - start) / entry["fps"], 2),
                hips_height_m=round(sum(s[3] for s in samples) / max(1, len(samples)), 3),
                path_length_m=round(sum(speeds) * step / entry["fps"], 2),
                max_speed_1s=round(max(smooth), 2) if smooth else 0,
                speed_per_second=[round(v, 2) for v in smooth],
                extent_xy=[
                    round(min(s[1] for s in samples), 2), round(max(s[1] for s in samples), 2),
                    round(min(s[2] for s in samples), 2), round(max(s[2] for s in samples), 2),
                ] if samples else [],
            )
        )
    report.append(entry)
    print(fbx.name, "ok")

out_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
