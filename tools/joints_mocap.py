"""Export joint positions for selected clips (blender -b -P joints_mocap.py -- <dir> <out.json>)."""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1 :]
folder, out_path = Path(args[0]), Path(args[1])
CLIPS = {  # file: (label, start_s, seconds)
    "Movimentos02.fbx": ("caminhada (Movimentos02, 30 s)", 30.0, 1.2),
    "Movimentos03.fbx": ("corrida (Movimentos03, 8,6 s)", 8.6, 0.8),
}
out = []
for name, (label, t0, dur) in CLIPS.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(folder / name), automatic_bone_orientation=True)
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    fps = scene.render.fps / scene.render.fps_base
    start = int(arm.animation_data.action.frame_range[0])
    frames = [start + int((t0 + i * dur / 7) * fps) for i in range(8)]
    poses = []
    for f in frames:
        scene.frame_set(f)
        bones = {}
        for b in arm.pose.bones:
            short = b.name.rsplit(":", 1)[-1]
            h = arm.matrix_world @ b.head
            t = arm.matrix_world @ b.tail
            bones[short] = [list(h), list(t)]
        poses.append(dict(frame=f, bones=bones))
    out.append(dict(label=label, poses=poses))
out_path.write_text(json.dumps(out), encoding="utf-8")
