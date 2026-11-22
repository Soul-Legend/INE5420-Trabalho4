"""Builds the animated character for the game from the class motion capture.

Run (headless):
    blender -b --factory-startup -P blender/build_character.py

Steps
1. Import the class captures (FBX, 120 fps, 28 bones, centimetres, Y up).
2. Create a clean rig: same bones and rest pose, metres, Z up, short names.
3. For each clip (idle, walk, run) search the capture for the pair of frames
   whose poses are most similar, so the clip loops seamlessly.
4. Remove the horizontal travel and the heading drift of the hips: the clip
   plays "in place" facing -Y and the game controller moves the character.
5. Spread the small remaining start/end difference over the clip.
6. Build a placeholder mannequin: one rigid piece per bone (a classic
   hierarchical model). It will be replaced by the group's character.
7. Export GLB (mesh + skeleton + 3 animations) and clips.json (speeds).
"""

import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT.parent / "capturas Aldo 2026.2"
OUT_GLB = ROOT / "game" / "assets" / "manequim.glb"
OUT_JSON = ROOT / "game" / "assets" / "clips.json"
OUT_BLEND = ROOT / "blender" / "manequim.blend"

SOURCE_FPS = 120
OUT_FPS = 30
FIRST_FRAME = 2  # first keyed frame of every capture
PREFIX = "Elisa:Solving:"

# name: (allowed loop length in seconds, candidate (file, window in seconds)).
# Candidate windows come from tools/gait_mocap.py (docs/mocap-trechos.json):
# every capture segment classified as standing, walking or running.
CLIPS = {
    "idle": ((2.0, 3.5), [("Movimentos02.fbx", (15.0, 23.0))]),
    "walk": ((1.8, 2.6), [
        ("Movimentos02.fbx", (24.0, 42.0)), ("Movimentos02.fbx", (60.0, 74.0)),
        ("Movimentos01.fbx", (5.0, 16.0)), ("Movimentos05.fbx", (10.0, 16.0)),
        ("Movimentos05.fbx", (40.0, 44.0)), ("Movimentos05.fbx", (49.0, 56.0)),
        ("Movimentos_basquete01.fbx", (33.0, 39.0)), ("Movimentos_basquete01.fbx", (90.0, 98.0)),
    ]),
    "run": ((0.55, 1.6), [
        ("Movimentos03.fbx", (7.5, 11.5)), ("Movimentos06.fbx", (18.5, 21.5)),
        ("Movimentos04.fbx", (16.5, 19.5)), ("Movimentos04.fbx", (2.5, 5.5)),
        ("Movimentos02.fbx", (9.5, 12.5)), ("Movimentos05.fbx", (15.5, 18.5)),
    ]),
}


# --------------------------------------------------------------- utilities
def clean(m: Matrix) -> Matrix:
    """Removes scale (the capture armature is scaled by 0.01)."""
    loc, rot, _ = m.decompose()
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4()


def short(name: str) -> str:
    return name.replace(PREFIX, "")


def import_capture(file_name: str):
    for obj in list(bpy.data.objects):
        if obj.get("capture"):
            bpy.data.objects.remove(obj, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=str(CAPTURES / file_name), automatic_bone_orientation=True
    )
    arm = next(o for o in set(bpy.data.objects) - before if o.type == "ARMATURE")
    for obj in set(bpy.data.objects) - before:
        obj["capture"] = True
    return arm


def world_pose(arm, frame: int) -> dict[str, Matrix]:
    """World matrix (metres, no scale) of every bone at a source frame."""
    bpy.context.scene.frame_set(frame)
    return {short(pb.name): clean(arm.matrix_world @ pb.matrix) for pb in arm.pose.bones}


def heading(m: Matrix) -> float:
    """Yaw of the hips: direction of the bone's local Z (front of the body) on the floor."""
    front = m.to_3x3().col[2]
    return math.atan2(front.y, front.x)


# ------------------------------------------------------------- clean rig
def build_rig(capture):
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = rig.data.name = "Rig"
    edit = rig.data.edit_bones
    edit.remove(edit[0])
    rest = {}
    for bone in capture.data.bones:  # parents come before children
        m = clean(capture.matrix_world @ bone.matrix_local)
        eb = edit.new(short(bone.name))
        eb.head, eb.tail = (0, 0, 0), (0, bone.length * 0.01, 0)
        eb.matrix = m
        if bone.parent:
            eb.parent = edit[short(bone.parent.name)]
        rest[eb.name] = m
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return rig, rest


def local_basis(rig, rest, targets: dict[str, Matrix]) -> dict[str, Matrix]:
    """Converts target armature-space matrices into pose-bone basis matrices.

    pose(b) = pose(parent) . rest(parent)^-1 . rest(b) . basis(b)
    """
    basis = {}
    for bone in rig.data.bones:
        name = bone.name
        if bone.parent:
            p = bone.parent.name
            rel = rest[p].inverted() @ rest[name]
            basis[name] = rel.inverted() @ targets[p].inverted() @ targets[name]
        else:
            basis[name] = rest[name].inverted() @ targets[name]
    return basis


# ----------------------------------------------------------- clip search
def pose_distance(a: dict, b: dict, bone_names) -> float:
    """Sum of joint-angle differences, ignoring where the body is and faces."""
    total = 0.0
    for name in bone_names:
        qa, qb = a[name].to_quaternion(), b[name].to_quaternion()
        total += qa.rotation_difference(qb).angle
    return total


def relative_frames(frames):
    """Bone matrices relative to the hips (position/heading independent)."""
    out = []
    for f in frames:
        hips = f["Hips"]
        inv = hips.inverted()
        rel = {k: inv @ v for k, v in f.items() if k != "Hips"}
        rel["Hips"] = Matrix.Rotation(-heading(hips), 4, "Z") @ hips  # keep tilt
        rel["Hips"].translation = (0, 0, hips.translation.z)
        out.append(rel)
    return out


def choose_loop(frames, length_range):
    """Returns (start, end) sample indices of the best seamless loop."""
    rel = relative_frames(frames)
    names = [k for k in rel[0] if not k.endswith("End") and "Thumb" not in k]
    lo, hi = (int(v * OUT_FPS) for v in length_range)
    best = None
    for s in range(0, len(frames) - lo):
        for e in range(s + lo, min(len(frames), s + hi + 1)):
            cost = pose_distance(rel[s], rel[e], names)
            # Prefer straight paths: compare travelled path with the chord.
            path = sum(
                (frames[i + 1]["Hips"].translation.xy - frames[i]["Hips"].translation.xy).length
                for i in range(s, e)
            )
            chord = (frames[e]["Hips"].translation.xy - frames[s]["Hips"].translation.xy).length
            cost += 2.0 * max(0.0, path - chord)
            turn = abs(heading(frames[e]["Hips"]) - heading(frames[s]["Hips"]))
            cost += 3.0 * min(turn, 2 * math.pi - turn)
            if chord > 0.2:
                # The body must face where it travels (no sideways/backwards runs):
                # angle between the travel direction and the mean hips heading.
                travel = frames[e]["Hips"].translation.xy - frames[s]["Hips"].translation.xy
                cx = sum(math.cos(heading(frames[i]["Hips"])) for i in range(s, e + 1))
                cy = sum(math.sin(heading(frames[i]["Hips"])) for i in range(s, e + 1))
                off = abs(math.atan2(travel.y, travel.x) - math.atan2(cy, cx))
                cost += 4.0 * min(off, 2 * math.pi - off)
            if best is None or cost < best[0]:
                best = (cost, s, e)
    return best


def in_place(frames, s, e, travel: bool):
    """Applies C(t) = Rz(theta(t)) . T(-drift(t)) so the clip stays in place, facing -Y."""
    start = frames[s]["Hips"].translation.copy()
    end = frames[e]["Hips"].translation.copy()
    n = e - s
    if travel:
        direction = (end - start).xy
        yaw0 = math.atan2(direction.y, direction.x)
    else:
        yaw0 = heading(frames[s]["Hips"])
    yaw_s, yaw_e = heading(frames[s]["Hips"]), heading(frames[e]["Hips"])
    drift_turn = math.atan2(math.sin(yaw_e - yaw_s), math.cos(yaw_e - yaw_s))
    target = -math.pi / 2  # face -Y (Blender front); glTF converts it to +Z
    out = []
    for i in range(s, e + 1):
        u = (i - s) / n
        drift = start.lerp(end, u) if travel else start.copy()
        drift.z = 0.0
        theta = target - (yaw0 + drift_turn * u)
        c = Matrix.Rotation(theta, 4, "Z") @ Matrix.Translation(-drift)
        out.append({k: c @ v for k, v in frames[i].items()})
    return out


def close_loop(bases):
    """Spreads the start/end mismatch of each bone basis linearly over the clip."""
    n = len(bases) - 1
    first, last = bases[0], bases[-1]
    out = []
    for i, frame in enumerate(bases):
        u = i / n
        fixed = {}
        for name, m in frame.items():
            q0, q1 = first[name].to_quaternion(), last[name].to_quaternion()
            if q0.dot(q1) < 0:
                q1 = -q1
            delta = q0 @ q1.inverted()
            q = Quaternion().slerp(delta, u) @ m.to_quaternion()
            t = m.translation + (first[name].translation - last[name].translation) * u
            fixed[name] = Matrix.Translation(t) @ q.to_matrix().to_4x4()
        out.append(fixed)
    return out


def bake_action(rig, name, bases):
    rig.animation_data_create()
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    rig.animation_data.action = action
    previous = {}
    for frame, basis in enumerate(bases):
        for pb in rig.pose.bones:
            m = basis[pb.name]
            q = m.to_quaternion()
            if pb.name in previous and previous[pb.name].dot(q) < 0:
                q = -q  # keep quaternions on the same hemisphere (no flips)
            previous[pb.name] = q
            pb.location = m.translation
            pb.rotation_quaternion = q
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_quaternion", frame=frame)
    return action


# ------------------------------------------------------------- mannequin
PARTS = {  # bone: (radius at head, radius at tail) in metres
    "Hips": (0.12, 0.11), "Spine": (0.12, 0.15), "Head": (0.10, 0.10),
    "LeftShoulder": (0.05, 0.05), "RightShoulder": (0.05, 0.05),
    "LeftArm": (0.055, 0.045), "RightArm": (0.055, 0.045),
    "LeftForeArm": (0.045, 0.035), "RightForeArm": (0.045, 0.035),
    "LeftHand": (0.035, 0.03), "RightHand": (0.035, 0.03),
    "LeftHandThumb1": (0.015, 0.012), "RightHandThumb1": (0.015, 0.012),
    "LeftHandThumb2": (0.012, 0.01), "RightHandThumb2": (0.012, 0.01),
    "LeftUpLeg": (0.075, 0.055), "RightUpLeg": (0.075, 0.055),
    "LeftLeg": (0.055, 0.042), "RightLeg": (0.055, 0.042),
    "LeftFoot": (0.045, 0.04), "RightFoot": (0.045, 0.04),
    "LeftToeBase": (0.04, 0.03), "RightToeBase": (0.04, 0.03),
}
COLORS = {"torso": (0.85, 0.55, 0.2, 1), "limb": (0.25, 0.45, 0.75, 1), "joint": (0.15, 0.15, 0.18, 1)}


def material(name, rgba):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def build_mannequin(rig, rest):
    bm = bmesh.new()
    deform = bm.verts.layers.deform.verify()  # per-vertex bone weights
    group_index = {bone.name: i for i, bone in enumerate(rig.data.bones)}
    mats = {key: i for i, key in enumerate(COLORS)}

    def add(bone, geom_verts, mat_key):
        # Rigid part: every vertex has weight 1 on this single bone.
        for v in geom_verts:
            v[deform][group_index[bone]] = 1.0
        faces = {f for v in geom_verts for f in v.link_faces}
        for f in faces:
            f.material_index = mats[mat_key]

    for bone in rig.data.bones:
        if bone.name not in PARTS:
            continue
        r0, r1 = PARTS[bone.name]
        m = rest[bone.name]
        length = bone.length
        if bone.name == "Head":
            res = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r0,
                                            matrix=m @ Matrix.Translation((0, length * 0.5, 0)))
            add(bone.name, res["verts"], "torso")
            continue
        # Cone along the bone (+Y): create_cone builds along Z, so rotate Z->Y.
        place = m @ Matrix.Translation((0, length / 2, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "X")
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r0, radius2=r1,
                                    depth=length, matrix=place)
        key = "torso" if bone.name in ("Hips", "Spine") else "limb"
        add(bone.name, res["verts"], key)
        if bone.name not in ("Hips", "Spine") and "Thumb" not in bone.name:
            res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r0 * 1.05,
                                            matrix=m)
            add(bone.name, res["verts"], "joint")
    mesh = bpy.data.meshes.new("Manequim")
    bm.to_mesh(mesh)
    bm.free()
    for key, rgba in COLORS.items():
        mesh.materials.append(material(f"manequim_{key}", rgba))
    obj = bpy.data.objects.new("Manequim", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for bone in rig.data.bones:  # same order as group_index above
        obj.vertex_groups.new(name=bone.name)
    obj.parent = rig
    obj.modifiers.new("Armature", "ARMATURE").object = rig
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


# ------------------------------------------------------------------ main
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = OUT_FPS

    rig = rest = None
    summary = {}
    step = SOURCE_FPS // OUT_FPS
    for clip, (length_range, candidates) in CLIPS.items():
        best = None
        for file_name, (t0, t1) in candidates:
            capture = import_capture(file_name)
            if rig is None:
                rig, rest = build_rig(capture)
            first = FIRST_FRAME + int(t0 * SOURCE_FPS)
            last = FIRST_FRAME + int(t1 * SOURCE_FPS)
            frames = [world_pose(capture, f) for f in range(first, last + 1, step)]
            cost, s, e = choose_loop(frames, length_range)
            print(f"  {clip:5s} {file_name} {t0}-{t1}s: cost {cost:.2f} at {t0 + s / OUT_FPS:.2f}s")
            if best is None or cost < best[0]:
                best = (cost, s, e, frames, file_name, t0)
        cost, s, e, frames, file_name, t0 = best
        travel = clip != "idle"
        placed = in_place(frames, s, e, travel)
        bases = close_loop([local_basis(rig, rest, f) for f in placed])
        bake_action(rig, clip, bases[:-1])  # last frame == first: drop it
        distance = (frames[e]["Hips"].translation.xy - frames[s]["Hips"].translation.xy).length
        seconds = (e - s) / OUT_FPS
        summary[clip] = dict(
            source=file_name,
            source_seconds=[round(t0 + s / OUT_FPS, 2), round(t0 + e / OUT_FPS, 2)],
            length_s=round(seconds, 3),
            frames=e - s,
            speed_m_s=round(distance / seconds, 3) if travel else 0.0,
            loop_cost=round(cost, 3),
        )
        print(clip, summary[clip])

    for obj in [o for o in bpy.data.objects if o.get("capture")]:
        bpy.data.objects.remove(obj, do_unlink=True)
    # Importing an FBX resets the scene to the capture rate (120 fps). The clips
    # were keyed at OUT_FPS, and glTF export converts frames to seconds with the
    # scene rate, so it must be restored or every clip plays 4x too fast.
    scene.render.fps, scene.render.fps_base = OUT_FPS, 1.0
    for action in list(bpy.data.actions):  # drop the full-length capture takes
        if action.name not in CLIPS:
            bpy.data.actions.remove(action)
    rig.animation_data.action = bpy.data.actions["idle"]
    build_mannequin(rig, rest)

    OUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB),
        export_format="GLB",
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_frame_step=1,
        export_anim_slide_to_zero=True,
    )
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
