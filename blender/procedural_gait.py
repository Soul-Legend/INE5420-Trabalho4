"""Procedural idle / walk / run cycles for the motion-capture rig ("pro" set).

Run on a .blend that contains the rig (manequim.blend or personagem.blend):
    blender -b blender/personagem.blend -P blender/procedural_gait.py -- [--export out.glb]

Each cycle is a periodic function of the phase phi in [0, 1), so it loops
perfectly. Per frame:
1. Hips: height bob, lateral sway, pelvis yaw/roll and forward lean.
2. Feet: stance (planted, sliding back at exactly the walking speed, so the
   feet never skate in the game) and swing (eased arc forward with lift);
   heel-strike and toe-off foot pitch.
3. Legs: analytic two-bone IK (law of cosines) from the hip to the ankle, knee
   pole pointing forward.
4. Spine counter-rotates the pelvis, head stays level, arms swing opposite to
   the legs with bent elbows.

Every bone gets a desired GLOBAL delta rotation D_b (relative to its rest
orientation, in armature space). The pose-bone basis follows from forward
kinematics G_b = G_parent . (R_parent^-1 R_b) . L_b:
    L_b = R_b^-1 . D_parent^-1 . D_b . R_b        (rotation part)
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
FPS = 30

# name: cycle seconds, speed m/s, stance fraction, step height, hips drop,
#       bob, sway, pelvis yaw, pelvis roll, lean, arm swing, elbow, abduction (degrees)
GAITS = {
    "walk_pro": dict(T=1.1, v=1.35, duty=0.62, lift=0.09, drop=0.035, bob=0.022, sway=0.022,
                     yaw=7, roll=4, lean=3, arm=22, elbow=18, abduct=9, run=False),
    "run_pro": dict(T=0.7, v=2.8, duty=0.36, lift=0.20, drop=0.085, bob=0.035, sway=0.012,
                    yaw=10, roll=3, lean=11, arm=38, elbow=85, abduct=12, run=True),
}


def smooth(u):
    return u * u * (3 - 2 * u)


class Rig:
    def __init__(self, obj):
        self.obj = obj
        self.bones = obj.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in self.bones}
        self.rest_rot = {n: m.to_quaternion() for n, m in self.rest.items()}
        head = lambda n: self.bones[n].head_local.copy()
        self.head = head
        toe, ankle = head("LeftToeBase"), head("LeftFoot")
        fwd = Vector((toe.x - ankle.x, toe.y - ankle.y, 0)).normalized()
        self.F = fwd                       # character forward
        self.U = Vector((0, 0, 1))         # up
        self.R = fwd.cross(self.U)         # character right
        self.hips0 = head("Hips")
        self.ankle_h = {s: head(f"{s}Foot").z for s in ("Left", "Right")}
        self.l1 = (head("LeftLeg") - head("LeftUpLeg")).length
        self.l2 = (head("LeftFoot") - head("LeftLeg")).length

    def dir(self, a, b):
        return (self.head(b) - self.head(a)).normalized()


def aim(rest_dir, parent_D, desired):
    """Global delta that turns a bone (already carried by its parent) to `desired`."""
    carried = parent_D @ rest_dir
    return carried.rotation_difference(desired) @ parent_D


def axis_rot(axis, deg):
    return Quaternion(axis, math.radians(deg))


def leg_ik(rig, hip, ankle_target):
    d = ankle_target - hip
    L = min(d.length, (rig.l1 + rig.l2) * 0.999)
    dn = d.normalized()
    a = (rig.l1 ** 2 - rig.l2 ** 2 + L ** 2) / (2 * L)
    h = math.sqrt(max(rig.l1 ** 2 - a * a, 0.0))
    pole = rig.F - dn * rig.F.dot(dn)       # knee points forward
    pole = pole.normalized() if pole.length > 1e-6 else rig.F
    knee = hip + dn * a + pole * h
    return (knee - hip).normalized(), (hip + dn * L - knee).normalized()


def pose_gait(rig, g, phi):
    """Global deltas D (quaternions) and hips translation for one phase."""
    F, U, Rt = rig.F, rig.U, rig.R
    T, v, duty = g["T"], g["v"], g["duty"]
    stride = v * T
    D = {}
    # Hips: two bobs per cycle. Walk: high at mid-stance; run: low at mid-stance.
    bob_phase = math.cos(4 * math.pi * (phi - duty / 2))
    bob = g["bob"] * (-bob_phase if g["run"] else bob_phase)
    sway = g["sway"] * math.sin(2 * math.pi * (phi - duty / 2))
    hips_t = U * (bob - g["drop"]) + Rt * sway
    yaw = g["yaw"] * math.sin(2 * math.pi * phi)
    roll = g["roll"] * math.sin(2 * math.pi * (phi - duty / 2))
    D_hips = axis_rot(U, yaw) @ axis_rot(F, roll) @ axis_rot(Rt, -g["lean"] * 0.4)
    D["Hips"] = D_hips
    # Chest counter-rotates the pelvis (net yaw opposite to the hips) and leans forward.
    D["Spine"] = axis_rot(U, -0.6 * yaw) @ axis_rot(Rt, -g["lean"] * 1.6)
    D["Head"] = axis_rot(Rt, g["lean"] * 0.8 + 1.5 * math.sin(4 * math.pi * phi))
    D["Head_End"] = D["Head"]
    hips_pos = rig.hips0 + hips_t

    for side, offset in (("Left", 0.0), ("Right", 0.5)):
        p = (phi + offset) % 1.0
        if p < duty:  # stance: planted foot slides back at the walking speed
            u = p / duty
            along = stride * duty * (0.5 - u)
            lift = 0.0
            pitch = (12 if not g["run"] else 4) * max(0.0, 1 - u / 0.15)  # heel strike: toe up
            pitch -= 28 * smooth(max(0.0, (u - 0.7) / 0.3))                # toe-off: heel rises
        else:         # swing: eased arc forward
            u = (p - duty) / (1 - duty)
            e = smooth(u)
            along = stride * duty * (e - 0.5)
            lift = g["lift"] * math.sin(math.pi * u)
            pitch = -25 * (1 - smooth(min(1.0, u / 0.4))) + 10 * smooth(max(0.0, (u - 0.6) / 0.4))
        foot_len = (rig.head(f"{side}ToeBase") - rig.head(f"{side}Foot")).length
        heel_raise = foot_len * math.sin(math.radians(-min(pitch, 0.0)))
        # Rest ankle, moved along the walking direction relative to the hips and lifted.
        rest_ankle = rig.head(f"{side}Foot")
        ankle = rest_ankle + F * (rig.hips0.dot(F) + along - rest_ankle.dot(F)) + U * (lift + heel_raise)
        hip =hips_pos + D_hips @ (rig.head(f"{side}UpLeg") - rig.hips0)
        thigh, shin = leg_ik(rig, hip, ankle)
        D[f"{side}UpLeg"] = aim(rig.dir(f"{side}UpLeg", f"{side}Leg"), D_hips, thigh)
        D[f"{side}Leg"] = aim(rig.dir(f"{side}Leg", f"{side}Foot"), D[f"{side}UpLeg"], shin)
        D_foot = axis_rot(Rt, pitch)
        D[f"{side}Foot"] = D_foot
        toe_flat = p < duty and pitch < 0
        D[f"{side}ToeBase"] = Quaternion() if toe_flat else D_foot
        D[f"{side}ToeEnd"] = D[f"{side}ToeBase"]

        # Arms swing opposite to the leg of the same side.
        swing = -g["arm"] * math.cos(2 * math.pi * (p - duty / 2))
        out = 1 if side == "Left" else -1
        D[f"{side}Shoulder"] = D["Spine"]
        hang = axis_rot(F, -out * g["abduct"]) @ axis_rot(Rt, swing) @ (-U)
        D[f"{side}Arm"] = aim(rig.dir(f"{side}Arm", f"{side}ForeArm"), D["Spine"], hang)
        elbow = g["elbow"] + (10 if g["run"] else 6) * max(0.0, math.sin(math.radians(swing)) * 3)
        fore = axis_rot(F, -out * g["abduct"] * 0.6) @ axis_rot(Rt, swing + elbow) @ (-U)
        D[f"{side}ForeArm"] = aim(rig.dir(f"{side}ForeArm", f"{side}Hand"), D[f"{side}Arm"], fore)
        for n in ("Hand", "HandThumb1", "HandThumb2", "HandEnd"):
            D[f"{side}{n}"] = D[f"{side}ForeArm"]
    return D, hips_t


def pose_idle(rig, phi):
    """Relaxed standing: slow breathing and a light weight shift."""
    g = dict(T=3.0, v=0.0, duty=1.0, lift=0, drop=0.02, bob=0, sway=0, yaw=0, roll=0, lean=0,
             arm=0, elbow=12, abduct=8, run=False)
    F, U, Rt = rig.F, rig.U, rig.R
    breath = math.sin(2 * math.pi * phi)
    shift = 0.012 * math.sin(2 * math.pi * phi)
    D = {"Hips": axis_rot(F, 1.2 * math.sin(2 * math.pi * phi))}
    D["Spine"] = axis_rot(Rt, -1.0 - 1.2 * breath)
    D["Head"] = D["Head_End"] = axis_rot(Rt, 1.5 * breath) @ axis_rot(U, 3 * math.sin(2 * math.pi * phi))
    hips_t = U * (-g["drop"] + 0.004 * breath) + Rt * shift
    hips_pos = rig.hips0 + hips_t
    for side in ("Left", "Right"):
        ankle = rig.head(f"{side}Foot")
        hip = hips_pos + D["Hips"] @ (rig.head(f"{side}UpLeg") - rig.hips0)
        thigh, shin = leg_ik(rig, hip, ankle)
        D[f"{side}UpLeg"] = aim(rig.dir(f"{side}UpLeg", f"{side}Leg"), D["Hips"], thigh)
        D[f"{side}Leg"] = aim(rig.dir(f"{side}Leg", f"{side}Foot"), D[f"{side}UpLeg"], shin)
        D[f"{side}Foot"] = D[f"{side}ToeBase"] = D[f"{side}ToeEnd"] = Quaternion()
        out = 1 if side == "Left" else -1
        D[f"{side}Shoulder"] = D["Spine"]
        sway = 2.5 * breath
        hang = axis_rot(F, -out * 8) @ axis_rot(Rt, sway) @ (-U)
        D[f"{side}Arm"] = aim(rig.dir(f"{side}Arm", f"{side}ForeArm"), D["Spine"], hang)
        fore = axis_rot(F, -out * 5) @ axis_rot(Rt, sway + 12) @ (-U)
        D[f"{side}ForeArm"] = aim(rig.dir(f"{side}ForeArm", f"{side}Hand"), D[f"{side}Arm"], fore)
        for n in ("Hand", "HandThumb1", "HandThumb2", "HandEnd"):
            D[f"{side}{n}"] = D[f"{side}ForeArm"]
    return D, hips_t


def bake(rig, name, frames, pose_fn):
    obj = rig.obj
    old = bpy.data.actions.get(name)
    if old:
        bpy.data.actions.remove(old)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    obj.animation_data_create()
    obj.animation_data.action = action
    previous = {}
    for frame in range(frames):
        D, hips_t = pose_fn(frame / frames)
        for pb in obj.pose.bones:
            b = rig.bones[pb.name]
            Db = D.get(pb.name, Quaternion())
            Dp = D.get(b.parent.name, Quaternion()) if b.parent else Quaternion()
            R = rig.rest_rot[pb.name]
            q = R.conjugated() @ Dp.conjugated() @ Db @ R
            q.normalize()
            if pb.name in previous and previous[pb.name].dot(q) < 0:
                q = -q
            previous[pb.name] = q
            pb.rotation_quaternion = q
            pb.location = (R.conjugated() @ hips_t) if b.parent is None else Vector()
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            pb.keyframe_insert("location", frame=frame)
    return action


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = args[args.index("--export") + 1] if "--export" in args else None
    bpy.context.scene.render.fps, bpy.context.scene.render.fps_base = FPS, 1.0
    rig = Rig(bpy.data.objects["Rig"])
    speeds = {}
    for name, g in GAITS.items():
        frames = round(g["T"] * FPS)
        bake(rig, name, frames, lambda phi, g=g: pose_gait(rig, g, phi))
        speeds[name] = dict(speed_m_s=g["v"], length_s=frames / FPS, frames=frames, procedural=True)
    bake(rig, "idle_pro", 90, lambda phi: pose_idle(rig, phi))
    speeds["idle_pro"] = dict(speed_m_s=0.0, length_s=3.0, frames=90, procedural=True)
    rig.obj.animation_data.action = bpy.data.actions["idle_pro"]

    clips_path = ROOT / "game" / "assets" / "clips.json"
    clips = json.loads(clips_path.read_text(encoding="utf-8")) if clips_path.exists() else {}
    clips.update(speeds)
    clips_path.write_text(json.dumps(clips, indent=2), encoding="utf-8")
    print("PRO", speeds, "forward", tuple(round(c, 3) for c in rig.F))
    bpy.ops.wm.save_mainfile()
    if out:
        bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animation_mode="ACTIONS",
                                  export_force_sampling=True, export_anim_slide_to_zero=True)


main()
