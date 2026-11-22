""""Untreated" capture clip, only for comparison (video demo_mocap_sem_tratamento).

A walking window of ONE take (Movimentos02, 24.0-26.6 s, same length as the
treated walk clip) baked onto the character rig exactly as recorded:
no loop-point search, no removal of the hips travel, no heading alignment
and no start/end correction. Only the skeleton is the same as the character's.

Run: blender -b blender/personagem.blend -P blender/bake_raw_clip.py -- --export game/assets/personagem.glb
"""
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_mocap_full import ROOT, bake_take  # noqa: E402

TAKE, WINDOW = "Movimentos02", (24.0, 26.6)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = args[args.index("--export") + 1] if "--export" in args else None
    rig = bpy.data.objects["Rig"]
    rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
    info = bake_take(rig, rest, TAKE, seconds=WINDOW, name="walk_raw")
    bone_names = {b.name for b in rig.data.bones}
    for action in list(bpy.data.actions):  # capture takes, and any action named like a bone
        if "|" in action.name or action.name in bone_names:
            bpy.data.actions.remove(action)
    scene = bpy.context.scene
    scene.render.fps, scene.render.fps_base = 30, 1.0  # FBX import set it to 120
    rig.animation_data.action = bpy.data.actions.get("idle_pro")
    clips_path = ROOT / "game" / "assets" / "clips.json"
    clips = json.loads(clips_path.read_text(encoding="utf-8"))
    clips["walk_raw"] = dict(source=f"{TAKE}.fbx", source_seconds=list(WINDOW), length_s=info["seconds"],
                             frames=info["frames"], untreated=True)
    clips_path.write_text(json.dumps(clips, indent=2), encoding="utf-8")
    print("RAW", info)
    bpy.ops.wm.save_mainfile()
    if out:
        bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animation_mode="ACTIONS",
                                  export_force_sampling=True, export_anim_slide_to_zero=True)


main()
