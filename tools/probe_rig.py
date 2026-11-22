"""Print how Blender imports the class mocap rig (blender -b -P probe_rig.py -- file.fbx)."""
import sys

import bpy

path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=True)
arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
print("object matrix_world:\n", arm.matrix_world)
print("scale", arm.scale[:], "rot", arm.rotation_euler[:], "parent", arm.parent)
print("rotation modes:", {pb.rotation_mode for pb in arm.pose.bones})
act = arm.animation_data.action
print("action", act.name, "range", act.frame_range[:], "slots", [s.name_display for s in getattr(act, "slots", [])])
paths = {}
for fc in act.fcurves if hasattr(act, "fcurves") else []:
    paths.setdefault(fc.data_path.split("].")[-1], 0)
    paths[fc.data_path.split("].")[-1]] += 1
print("fcurve kinds", paths)
for b in arm.data.bones[:6]:
    print(b.name, "head_local", tuple(round(v, 3) for v in b.head_local), "len", round(b.length, 3), "parent", b.parent.name if b.parent else None)
bpy.context.scene.frame_set(1000)
h = arm.pose.bones[arm.data.bones[0].name]
print("hips world head @1000:", arm.matrix_world @ h.head, "y axis", (arm.matrix_world.to_3x3() @ h.matrix.to_3x3()).col[1])
print("scene fps", bpy.context.scene.render.fps, "unit scale", bpy.context.scene.unit_settings.scale_length)
