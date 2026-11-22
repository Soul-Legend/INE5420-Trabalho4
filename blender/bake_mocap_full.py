"""Bakes the COMPLETE class capture takes onto the character rig (root motion kept).

Run on a .blend with the rig (e.g. personagem.blend):
    blender -b blender/personagem.blend -P blender/bake_mocap_full.py -- [--export out.glb]

Unlike the game clips (in place, looped), these actions keep the hips
trajectory recorded in the capture room, so the character walks around as
the student did. They drive the scripted "MoCap show" in the game.
Keyframes are written in bulk through F-curves (tens of thousands of frames).
"""

import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_character import (  # noqa: E402
    CAPTURES, FIRST_FRAME, OUT_FPS, SOURCE_FPS, import_capture, local_basis, world_pose,
)

ROOT = Path(__file__).resolve().parents[1]
TAKES = ["Movimentos01", "Movimentos02", "Movimentos03", "Movimentos04", "Movimentos05",
         "Movimentos06", "Movimentos07", "Movimentos_basquete01"]


def bake_take(rig, rest, take, seconds=None, name=None):
    """seconds=(t0, t1) bakes only that window of the take; name overrides the action name."""
    capture = import_capture(f"{take}.fbx")
    start, end = (int(v) for v in capture.animation_data.action.frame_range)
    step = SOURCE_FPS // OUT_FPS
    source_frames = list(range(max(start, FIRST_FRAME), end + 1, step))
    if seconds:
        lo, hi = (FIRST_FRAME + int(t * SOURCE_FPS) for t in seconds)
        source_frames = [f for f in source_frames if lo <= f <= hi]
    rot = {b.name: [] for b in rig.data.bones}
    loc = {b.name: [] for b in rig.data.bones}
    previous = {}
    for f in source_frames:
        basis = local_basis(rig, rest, world_pose(capture, f))
        for bone_name, m in basis.items():
            q = m.to_quaternion()
            if bone_name in previous and previous[bone_name].dot(q) < 0:
                q = -q  # continuous quaternions (no flips between frames)
            previous[bone_name] = q
            rot[bone_name].append(q)
            loc[bone_name].append(m.translation)
    bpy.data.objects.remove(capture, do_unlink=True)

    name = name or f"mocap_{take}"
    old = bpy.data.actions.get(name)
    if old:
        bpy.data.actions.remove(old)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    rig.animation_data.action = action
    n = len(source_frames)
    for bone in rig.data.bones:
        for prop, values, size in (("rotation_quaternion", rot[bone.name], 4), ("location", loc[bone.name], 3)):
            path = f'pose.bones["{bone.name}"].{prop}'
            for i in range(size):
                fc = action.fcurve_ensure_for_datablock(rig, path, index=i, group_name=bone.name)
                fc.keyframe_points.add(n)
                co = []
                for k, v in enumerate(values):
                    co += [float(k), float(v[i])]
                fc.keyframe_points.foreach_set("co", co)
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
                fc.update()
    return dict(action=name, seconds=round((n - 1) / OUT_FPS, 2), frames=n)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = args[args.index("--export") + 1] if "--export" in args else None
    rig = bpy.data.objects["Rig"]
    rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
    rig.animation_data_create()
    takes = []
    for take in TAKES:
        info = bake_take(rig, rest, take)
        print("TAKE", info)
        takes.append(info)
    for action in list(bpy.data.actions):  # original capture takes ("Armature|...")
        if "|" in action.name:
            bpy.data.actions.remove(action)
    scene = bpy.context.scene
    scene.render.fps, scene.render.fps_base = OUT_FPS, 1.0  # FBX import set it to 120
    rig.animation_data.action = bpy.data.actions.get("idle_pro") or bpy.data.actions.get("idle")
    clips_path = ROOT / "game" / "assets" / "clips.json"
    clips = json.loads(clips_path.read_text(encoding="utf-8"))
    clips["mocap_takes"] = takes
    clips_path.write_text(json.dumps(clips, indent=2), encoding="utf-8")
    bpy.ops.wm.save_mainfile()
    if out:
        bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animation_mode="ACTIONS",
                                  export_force_sampling=True, export_anim_slide_to_zero=True)


if __name__ == "__main__":
    main()
