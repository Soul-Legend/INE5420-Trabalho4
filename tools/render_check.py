"""Render the mannequin in rest pose and in each clip (blender -b manequim.blend -P render_check.py -- out_dir)."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

out = Path(sys.argv[sys.argv.index("--") + 1])
out.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
rig = bpy.data.objects["Rig"]

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.location = (2.2, -3.2, 1.3)
direction = Vector((0, 0, 0.9)) - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.rotation_euler = (math.radians(50), 0, math.radians(30))
scene.collection.objects.link(sun)
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x, scene.render.resolution_y = 480, 480
scene.display.shading.color_type = "MATERIAL"

rig.data.pose_position = "REST"
scene.render.filepath = str(out / "rest.png")
bpy.ops.render.render(write_still=True)
rig.data.pose_position = "POSE"
for name in ["idle", "walk", "run"]:
    rig.animation_data.action = bpy.data.actions[name]
    if hasattr(rig.animation_data, "action_slot") and rig.animation_data.action.slots:
        rig.animation_data.action_slot = rig.animation_data.action.slots[0]
    for frame in (0, 8):
        scene.frame_set(frame)
        scene.render.filepath = str(out / f"{name}_{frame:02d}.png")
        bpy.ops.render.render(write_still=True)
