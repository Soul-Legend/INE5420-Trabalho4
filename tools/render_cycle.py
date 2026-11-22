"""Side-view strip of N frames of an action + foot-slide check.
blender -b file.blend -P render_cycle.py -- <action> <out.png> [frames=8]"""
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
action_name, out = args[0], args[1]
n = int(args[2]) if len(args) > 2 else 8
scene = bpy.context.scene
rig = bpy.data.objects["Rig"]
rig.animation_data.action = bpy.data.actions[action_name]
if rig.animation_data.action.slots:
    rig.animation_data.action_slot = rig.animation_data.action.slots[0]
start, end = (int(v) for v in rig.animation_data.action.frame_range)
length = end - start + 1

# Foot slide: during contact (toe near the floor) the toe should move back at constant speed.
toe = rig.pose.bones["LeftToeBase"]
track = []
for f in range(start, end + 1):
    scene.frame_set(f)
    p = rig.matrix_world @ toe.head
    track.append((f, p.y, p.z))
low = min(z for _, _, z in track)
contact = [(f, y) for f, y, z in track if z < low + 0.01]
if len(contact) > 2:
    speeds = [(b[1] - a[1]) * scene.render.fps for a, b in zip(contact, contact[1:]) if b[0] == a[0] + 1]
    print("TOE_CONTACT_FRAMES", len(contact), "speed m/s", [round(s, 2) for s in speeds[:12]])

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x, scene.render.resolution_y = 300, 420
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = 2.2
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = Vector((6, 0, 0.95))
cam.rotation_euler = Vector((-1, 0, 0)).to_track_quat("-Z", "Y").to_euler()
paths = []
for i in range(n):
    scene.frame_set(start + round(i * length / n))
    scene.render.filepath = f"{out}_{i}.png"
    bpy.ops.render.render(write_still=True)
    paths.append(scene.render.filepath)
print("FRAMES", ";".join(paths))
