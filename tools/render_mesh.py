"""Render a mesh file from front (-Y), side (+X) and back (blender -b -P render_mesh.py -- mesh.glb out_prefix)."""
import math
import sys

import bpy
from mathutils import Vector

mesh_path, prefix = sys.argv[sys.argv.index("--") + 1 :][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=mesh_path)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center, size = (lo + hi) / 2, max(hi - lo)
print("BBOX", tuple(round(v, 3) for v in lo), tuple(round(v, 3) for v in hi))
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = scene.render.resolution_y = 512
scene.display.shading.light = "STUDIO"
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = size * 1.15
scene.collection.objects.link(cam)
scene.camera = cam
for name, direction in (("front", Vector((0, -1, 0))), ("side", Vector((1, 0, 0))), ("back", Vector((0, 1, 0)))):
    cam.location = center + direction * size * 3
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)
