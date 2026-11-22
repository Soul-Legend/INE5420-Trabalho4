"""Find walking and running segments in mocap FBX files (blender -b -P gait_mocap.py -- <dir> <out.json>).

Running is detected by flight phases: frames where BOTH feet are off the ground.
"""
import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1 :]
folder, out_path = Path(args[0]), Path(args[1])
RATE = 30  # samples per second
report = []

for fbx in sorted(folder.glob("Movimentos*.fbx")):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True)
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    prefix = arm.data.bones[0].name.rsplit(":", 1)[0] + ":"
    pb = lambda n: arm.pose.bones[prefix + n]
    fps = scene.render.fps / scene.render.fps_base
    start, end = (int(v) for v in arm.animation_data.action.frame_range)
    step = int(fps // RATE)
    rows = []
    for f in range(start, end + 1, step):
        scene.frame_set(f)
        w = arm.matrix_world
        h = w @ pb("Hips").head
        lf = min((w @ pb("LeftFoot").head).z, (w @ pb("LeftToeBase").head).z)
        rf = min((w @ pb("RightFoot").head).z, (w @ pb("RightToeBase").head).z)
        rows.append((f, h.x, h.y, h.z, lf, rf))
    lows = sorted(min(r[4], r[5]) for r in rows)
    ground = lows[len(lows) // 20]
    lift = 0.06  # metres above ground that count as "off the ground"
    seconds = []
    for i in range(0, len(rows) - RATE, RATE):
        chunk = rows[i : i + RATE + 1]
        dist = sum(
            ((b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5 for a, b in zip(chunk, chunk[1:])
        )
        flight = sum(1 for r in chunk if r[4] > ground + lift and r[5] > ground + lift)
        bounce = max(r[3] for r in chunk) - min(r[3] for r in chunk)
        seconds.append(dict(t=round((chunk[0][0] - start) / fps, 1), frame=chunk[0][0], speed=round(dist, 2),
                            flight=flight, bounce=round(bounce, 3)))
    # Group consecutive seconds by gait label.
    def label(s):
        if s["speed"] < 0.4:
            return "parado"
        if s["flight"] >= 3 and s["speed"] >= 1.3:
            return "corrida"
        return "caminhada"
    segments = []
    for s in seconds:
        lab = label(s)
        if segments and segments[-1]["gait"] == lab:
            seg = segments[-1]
            seg["end_s"] = s["t"] + 1
            seg["end_frame"] = s["frame"] + int(fps)
            seg["speeds"].append(s["speed"])
            seg["flights"].append(s["flight"])
        else:
            segments.append(dict(gait=lab, start_s=s["t"], end_s=s["t"] + 1, start_frame=s["frame"],
                                 end_frame=s["frame"] + int(fps), speeds=[s["speed"]], flights=[s["flight"]]))
    for seg in segments:
        seg["mean_speed"] = round(sum(seg["speeds"]) / len(seg["speeds"]), 2)
        seg["dur_s"] = round(seg["end_s"] - seg["start_s"], 1)
    report.append(dict(file=fbx.name, ground=round(ground, 3), seconds=seconds,
                       segments=[{k: v for k, v in s.items() if k not in ("speeds",)} for s in segments]))
    print(fbx.name, "ok")

out_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
