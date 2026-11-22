"""Reproduces, for the report, the first mannequin bug (pieces bound to the wrong bones).

The first version of build_mannequin() computed each piece's vertex indices as
"the last len(verts) vertices of the bmesh". That assumption is wrong for the
geometry created by bmesh.ops, so some pieces were weighted to the wrong bone
and stretched into blades when animated. This script rebuilds the mannequin
with that OLD logic and renders it (rest + walk frames) next to the fixed one.

Run: blender -b blender/manequim.blend -P tools/reproduz_bug_manequim.py -- out.png
"""
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, bpy.path.abspath("//"))
from build_character import PARTS  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
rig = bpy.data.objects["Rig"]
rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}

bm = bmesh.new()
groups = {}


def add_old(bone, geom_verts):  # the original (wrong) index bookkeeping
    start = len(bm.verts) - len(geom_verts)
    groups.setdefault(bone, []).extend(range(start, len(bm.verts)))


for bone in rig.data.bones:
    if bone.name not in PARTS:
        continue
    r0, r1 = PARTS[bone.name]
    m, length = rest[bone.name], bone.length
    if bone.name == "Head":
        res = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r0,
                                        matrix=m @ Matrix.Translation((0, length * 0.5, 0)))
        add_old(bone.name, res["verts"])
        continue
    place = m @ Matrix.Translation((0, length / 2, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "X")
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r0, radius2=r1, depth=length, matrix=place)
    add_old(bone.name, res["verts"])
    if bone.name not in ("Hips", "Spine") and "Thumb" not in bone.name:
        res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r0 * 1.05, matrix=m)
        add_old(bone.name, res["verts"])

mesh = bpy.data.meshes.new("Bug")
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new("Bug", mesh)
bpy.context.scene.collection.objects.link(obj)
for bone, idx in groups.items():
    obj.vertex_groups.new(name=bone).add(idx, 1.0, "REPLACE")
obj.parent = rig
obj.modifiers.new("Armature", "ARMATURE").object = rig
fixed = bpy.data.objects.get("Manequim")
if fixed:
    fixed.hide_render = True

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x, scene.render.resolution_y = 360, 450
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
cam.location = (2.2, -3.2, 1.3)
cam.rotation_euler = (Vector((0, 0, 0.9)) - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
rig.animation_data.action = bpy.data.actions["walk"]
paths = []
for i, frame in enumerate((None, 0, 20, 40)):
    rig.data.pose_position = "REST" if frame is None else "POSE"
    if frame is not None:
        scene.frame_set(frame)
    scene.render.filepath = f"{out}_{i}.png"
    bpy.ops.render.render(write_still=True)
    paths.append(scene.render.filepath)
print("BUG_FRAMES", ";".join(paths))
