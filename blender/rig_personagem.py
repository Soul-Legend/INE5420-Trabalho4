"""Binds a generated character mesh (e.g. Hunyuan3D GLB) to the motion-capture rig.

Run:
    blender -b blender/manequim.blend -P blender/rig_personagem.py -- \
        <mesh.glb> [--yaw DEG] [--texture atlas.png] [--cut-bottom 0.012] [--out game/assets/personagem.glb]

Steps
1. Import the mesh, join every part into one object and apply its transform.
2. Rotate it (--yaw) so it faces -Y, like the rig.
3. Fit it to the rig rest pose (T-pose): uniform scale by the arm span,
   a limited vertical correction so the arms sit at shoulder height, and a
   translation that puts the feet on the floor and the body over the hips.
4. Decimate very dense meshes (keeps UVs/texture).
5. Parent to the rig with automatic weights (bone heat). If bone heat leaves
   vertices without weights, fill them from the nearest bones.
6. Export GLB with the mesh, the skeleton and the idle/walk/run animations.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
MAX_FACES = 40000


def parse_args():
    args = sys.argv[sys.argv.index("--") + 1 :]
    opts = {"mesh": args[0], "yaw": 0.0, "out": str(ROOT / "game" / "assets" / "personagem.glb"),
            "texture": ""}
    for key, value in zip(args[1::2], args[2::2]):
        opts[key.lstrip("-")] = value
    opts["yaw"] = float(opts["yaw"])
    return opts


def import_mesh(path: str):
    before = set(bpy.data.objects)
    if path.lower().endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in set(bpy.data.objects) - before]
    meshes = [o for o in new if o.type == "MESH"]
    for obj in meshes:  # keep world transform, drop glTF helper parents
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
    for obj in new:
        if obj.type != "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = obj.data.name = "Personagem"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # glTF splits vertices along UV/normal seams; bone heat needs a connected
    # surface, so merge coincident vertices (UVs live in face corners and survive).
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def clean_parts(obj):
    """Deletes loose parts that are not the character.

    - the "frame": a thin, flat part spanning most of the width and height
      (the image border, reconstructed when background removal is off);
    - debris: parts with less than 0.2% of the vertices.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    lo = Vector((min(v.co[i] for v in bm.verts) for i in range(3)))
    hi = Vector((max(v.co[i] for v in bm.verts) for i in range(3)))
    size = hi - lo
    seen, parts = set(), []
    for start in bm.verts:
        if start.index in seen:
            continue
        stack, part = [start], []
        seen.add(start.index)
        while stack:
            v = stack.pop()
            part.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        parts.append(part)
    removed = []
    for part in parts:
        plo = Vector((min(v.co[i] for v in part) for i in range(3)))
        phi = Vector((max(v.co[i] for v in part) for i in range(3)))
        psize = phi - plo
        frame = psize.x > 0.85 * size.x and psize.z > 0.85 * size.z and psize.y < 0.08 * size.z
        debris = len(part) < 0.002 * len(bm.verts)
        if frame or debris:
            removed.append(("frame" if frame else "debris", len(part)))
            bmesh.ops.delete(bm, geom=part, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return dict(parts=len(parts), removed=removed)


def cut_band(obj, side: str, fraction: float):
    """Deletes a thin horizontal band at the top or bottom of the mesh.

    Used to drop reconstruction leftovers glued to the character, e.g. the thin
    floor plate that Hunyuan3D builds from the shadow under the feet.
    """
    me = obj.data
    zs = [v.co.z for v in me.vertices]
    height = max(zs) - min(zs)
    bm = bmesh.new()
    bm.from_mesh(me)
    if side == "top":
        band = [v for v in bm.verts if v.co.z > max(zs) - fraction * height]
    else:
        band = [v for v in bm.verts if v.co.z < min(zs) + fraction * height]
    bmesh.ops.delete(bm, geom=band, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(band)


def project_texture(obj, atlas_path: str):
    """Front projection of the concept image (see ia/textura_projecao.py).

    UV u,v come from the vertex x,z mapped onto the character box in the image.
    Faces whose normal points backwards (+Y; the character faces -Y) sample the
    blurred right half of the atlas instead of the sharp left half.
    """
    import json

    bbox = json.loads(Path(atlas_path.replace("_atlas.png", "_bbox.json")).read_text())
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    uv = me.uv_layers.new(name="Projecao")
    me.uv_layers.active = uv
    for poly in me.polygons:
        back = poly.normal.y > 0.2
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u = bbox["x0"] + (co.x - x0) / (x1 - x0) * (bbox["x1"] - bbox["x0"])
            row = bbox["y0"] + (z1 - co.z) / (z1 - z0) * (bbox["y1"] - bbox["y0"])  # image rows go down
            uv.data[li].uv = ((0.5 if back else 0.0) + u / 2, 1.0 - row)
    for layer in [l for l in me.uv_layers if l.name != "Projecao"]:
        me.uv_layers.remove(layer)
    image = bpy.data.images.load(atlas_path)
    image.pack()
    mat = bpy.data.materials.new("Personagem_IA")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.7
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    me.materials.clear()
    me.materials.append(mat)


def rig_landmarks(rig):
    bones = rig.data.bones
    head = lambda n: rig.matrix_world @ bones[n].head_local
    tail = lambda n: rig.matrix_world @ bones[n].tail_local
    return dict(
        span=(tail("LeftHandEnd") - tail("RightHandEnd")).length,
        center_x=(tail("LeftHandEnd").x + tail("RightHandEnd").x) / 2,
        shoulder_z=(head("LeftArm").z + head("RightArm").z) / 2,
        feet_z=min(head("LeftToeBase").z, head("RightToeBase").z, head("LeftFoot").z) - 0.05,
        hips=head("Hips"),
    )


def mesh_landmarks(obj):
    verts = [v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]
    min_x, max_x = min(xs), max(xs)
    half = (max_x - min_x) / 2
    center_x = (min_x + max_x) / 2
    arms = sorted(v.z for v in verts if abs(v.x - center_x) > 0.7 * half)
    feet_z = min(v.z for v in verts)
    shoulder_z = arms[len(arms) // 2] if arms else feet_z + 0.8 * (max(v.z for v in verts) - feet_z)
    return dict(span=max_x - min_x, center_x=center_x, shoulder_z=shoulder_z, feet_z=feet_z)


def fit_to_rig(obj, rig, yaw_deg):
    obj.data.transform(Matrix.Rotation(math.radians(yaw_deg), 4, "Z"))
    target = rig_landmarks(rig)
    current = mesh_landmarks(obj)
    s = target["span"] / current["span"]
    obj.data.transform(Matrix.Scale(s, 4))
    current = mesh_landmarks(obj)
    sz = (target["shoulder_z"] - target["feet_z"]) / (current["shoulder_z"] - current["feet_z"])
    sz = max(0.8, min(1.25, sz))  # proportions only nudged, never distorted
    obj.data.transform(Matrix.Diagonal((1, 1, sz, 1)))
    current = mesh_landmarks(obj)
    torso = [v.co.y for v in obj.data.vertices if abs(v.co.x - current["center_x"]) < 0.15]
    center_y = sum(torso) / len(torso) if torso else 0.0
    shift = Vector((target["center_x"] - current["center_x"], target["hips"].y - center_y,
                    target["feet_z"] - current["feet_z"]))
    obj.data.transform(Matrix.Translation(shift))
    obj.data.update()
    return dict(scale=round(s, 4), vertical=round(sz, 3))


def decimate(obj):
    faces = len(obj.data.polygons)
    if faces <= MAX_FACES:
        return faces
    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.ratio = MAX_FACES / faces
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return len(obj.data.polygons)


def nearest_bone_weights(obj, rig, deform):
    """Fallback for vertices bone heat could not reach: weights from the 2 nearest bones."""
    segments = {
        b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local)
        for b in rig.data.bones if b.name in deform
    }
    groups = {name: obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name) for name in deform}
    fixed = 0
    for v in obj.data.vertices:
        if any(g.weight > 0 for g in v.groups):
            continue
        p = obj.matrix_world @ v.co
        dists = []
        for name, (a, b) in segments.items():
            ab = b - a
            t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
            dists.append(((a + ab * t - p).length, name))
        dists.sort()
        (d0, n0), (d1, n1) = dists[0], dists[1]
        w0, w1 = 1 / (d0 ** 4 + 1e-9), 1 / (d1 ** 4 + 1e-9)
        groups[n0].add([v.index], w0 / (w0 + w1), "REPLACE")
        groups[n1].add([v.index], w1 / (w0 + w1), "REPLACE")
        fixed += 1
    return fixed


def bind(obj, rig):
    deform = {b.name for b in rig.data.bones if not b.name.endswith("End")}
    for b in rig.data.bones:
        b.use_deform = b.name in deform
    rig.data.pose_position = "REST"
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    rig.data.pose_position = "POSE"
    unweighted = sum(1 for v in obj.data.vertices if not any(g.weight > 0 for g in v.groups))
    fixed = nearest_bone_weights(obj, rig, deform) if unweighted else 0
    return dict(vertices=len(obj.data.vertices), without_bone_heat=unweighted, filled=fixed)


def main():
    opts = parse_args()
    rig = bpy.data.objects["Rig"]
    old = bpy.data.objects.get("Manequim")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    obj = import_mesh(opts["mesh"])
    for side in ("top", "bottom"):
        if opts.get(f"cut-{side}"):
            print("CUT", side, cut_band(obj, side, float(opts[f"cut-{side}"])))
    cleaned = clean_parts(obj)
    print("CLEAN", cleaned)
    if opts["texture"]:
        project_texture(obj, str(Path(opts["texture"]).resolve()))
    fit = fit_to_rig(obj, rig, opts["yaw"])
    faces = decimate(obj)
    weights = bind(obj, rig)
    print("FIT", fit, "FACES", faces, "WEIGHTS", weights)
    rig.animation_data.action = bpy.data.actions["idle"]
    for action in list(bpy.data.actions):  # drop original capture takes ("Armature|...")
        if "|" in action.name:
            bpy.data.actions.remove(action)
    # Animations are keyed at 30 fps; glTF export uses the scene rate.
    bpy.context.scene.render.fps, bpy.context.scene.render.fps_base = 30, 1.0
    bpy.data.orphans_purge(do_recursive=True)  # drop the dense imported mesh data
    out = Path(opts["out"])
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blender" / (out.stem + ".blend")))
    bpy.ops.export_scene.gltf(
        filepath=str(out), export_format="GLB", export_animation_mode="ACTIONS",
        export_force_sampling=True, export_anim_slide_to_zero=True,
    )


main()
