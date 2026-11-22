"""Test input for rig_personagem.py: the mannequin fused into ONE watertight mesh,
exported at another scale and facing +Y, like an unknown generated model.

Run: blender -b blender/manequim.blend -P tools/make_proxy.py -- out.glb
"""
import math
import sys

import bpy
from mathutils import Matrix

out = sys.argv[sys.argv.index("--") + 1]
rig = bpy.data.objects["Rig"]
rig.data.pose_position = "REST"
src = bpy.data.objects["Manequim"]
proxy = src.copy()
proxy.data = src.data.copy()
bpy.context.scene.collection.objects.link(proxy)
bpy.context.view_layer.update()
bpy.context.view_layer.objects.active = proxy
for mod in list(proxy.modifiers):
    proxy.modifiers.remove(mod)
proxy.parent = None
proxy.vertex_groups.clear()
remesh = proxy.modifiers.new("Remesh", "REMESH")
remesh.mode = "VOXEL"
remesh.voxel_size = 0.02
bpy.ops.object.modifier_apply(modifier=remesh.name)
proxy.data.transform(Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Scale(0.6, 4))
for obj in list(bpy.data.objects):
    if obj is not proxy:
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
print("PROXY faces", len(proxy.data.polygons))
