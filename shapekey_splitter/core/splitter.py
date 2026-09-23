"""
Shape key splitting algorithm and output mesh/collection management.
"""

import numpy as np
import bpy

from . import centerline as cl_mod
from ..utils.mesh_utils import get_shape_key_positions, get_vertex_group_weights

# Temporary shape key used by preview mode — never split or exported
PREVIEW_KEY_NAME = "SKS_Preview"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _link_exclusively(new_obj, collection) -> None:
    collection.objects.link(new_obj)
    for coll in list(new_obj.users_collection):
        if coll != collection:
            coll.objects.unlink(new_obj)


def make_template_mesh(obj, ref_co: np.ndarray):
    """
    Return a copy of obj's mesh with all shape keys stripped and vertices set to
    the reference key positions. Copy this once per batch instead of copying
    (and then stripping) the full shape key stack for every output.
    """
    tmp_obj = obj.copy()
    tmp_obj.data = obj.data.copy()
    tmp_obj.shape_key_clear()
    mesh = tmp_obj.data
    bpy.data.objects.remove(tmp_obj, do_unlink=True)

    mesh.vertices.foreach_set("co", ref_co.reshape(-1))
    mesh.update()
    return mesh


def mask_output_name(mask) -> str:
    return mask.name.strip().lower().replace(" ", "_")


def split_candidates(obj) -> list:
    """Shape keys that get split: everything except the reference key and the preview key."""
    shape_keys = obj.data.shape_keys
    if shape_keys is None:
        return []
    ref = shape_keys.reference_key
    return [
        kb for kb in shape_keys.key_blocks
        if kb != ref and kb.name != PREVIEW_KEY_NAME
    ]


# ---------------------------------------------------------------------------
# Core split computation
# ---------------------------------------------------------------------------

class SplitContext:
    """
    Everything that is identical for every shape key in a batch: reference
    positions, center line weights and mask weights. Build once, reuse per key.
    """

    def __init__(self, obj, settings, masks=None):
        self.obj = obj
        self.settings = settings
        shape_keys = obj.data.shape_keys
        self.ref_co = get_shape_key_positions(shape_keys.reference_key)   # (N, 3)

        cl = settings.centerline
        self.weight_L, self.weight_R = cl_mod.compute_centerline_weights(
            self.ref_co[:, 0],
            cl.blend_falloff,
            cl.transition_type,
            cl.center_threshold,
        )

        if masks is None:
            masks = [m for m in settings.masks if m.enabled]
        # [(mask, (N,) weights)] — vertex group reads are slow, do them once
        self.masks = [(m, get_vertex_group_weights(obj, m.vertex_group)) for m in masks]


def shape_key_delta(kb) -> np.ndarray:
    """Delta of a key against its own relative key, as Blender evaluates it."""
    return get_shape_key_positions(kb) - get_shape_key_positions(kb.relative_key)


def split_shape_key(kb, ctx: SplitContext) -> dict:
    """
    Compute all split variants for one shape key.

    Returns:
        {output_name: (N, 3) float32 positions array}

    Output includes:
      - If include_full_lr: {sk_name}{sep}L  and  {sk_name}{sep}R  (pure centerline split)
      - Per active bilateral mask:  {sk_name}_{mask_name}{sep}L  and  ..._R
      - Per active single-side mask: {sk_name}_{mask_name}  (one output only; the
        painted mask alone decides the region, it is not gated by the center line)
    """
    ref_co = ctx.ref_co
    delta = shape_key_delta(kb)
    weight_L, weight_R = ctx.weight_L, ctx.weight_R
    settings = ctx.settings
    sk_name = kb.name

    def bake(w):
        return (ref_co + delta * w[:, np.newaxis]).astype(np.float32)

    sep = settings.naming_separator
    results = {}

    # --- Base L/R split (no mask) — optional ---
    if settings.include_full_lr:
        results[f"{sk_name}{sep}L"] = bake(weight_L)
        results[f"{sk_name}{sep}R"] = bake(weight_R)

    # --- Mask variants ---
    for mask, mask_w in ctx.masks:
        mask_name = mask_output_name(mask)

        if mask.is_bilateral:
            # Multiply user mask by centerline weights so the blend transition
            # is applied to the masked region, not just a hard zero at the axis.
            results[f"{sk_name}_{mask_name}{sep}L"] = bake(mask_w * weight_L)
            results[f"{sk_name}_{mask_name}{sep}R"] = bake(mask_w * weight_R)
        else:
            results[f"{sk_name}_{mask_name}"] = bake(mask_w)

    return results


# ---------------------------------------------------------------------------
# Output mesh / collection helpers
# ---------------------------------------------------------------------------

def create_split_mesh_object(obj, template_mesh, positions: np.ndarray, name: str, collection):
    """
    Duplicate the source object onto a copy of the key-less template mesh, bake
    the split positions into its vertices and link it to the collection.
    Any object with the same name already in the collection is replaced.
    """
    remove_object_from_collection(collection, name)

    new_mesh = template_mesh.copy()
    new_mesh.name = name
    new_mesh.vertices.foreach_set("co", positions.reshape(-1))
    new_mesh.update()

    new_obj = obj.copy()
    new_obj.data = new_mesh
    new_obj.name = name
    new_obj.hide_render = True
    _link_exclusively(new_obj, collection)
    return new_obj


def build_preview_mesh(obj, template_mesh, outputs: list, collection):
    """
    Build {obj.name}_Preview: a full duplicate of the source mesh with every
    split result added as a shape key (all at value 0.0 by default).

    outputs: [(shape_key_name, (N, 3) positions)] — names are the intended
    output names, independent of any suffix Blender gave the split objects.
    """
    preview_name = f"{obj.name}_Preview"
    remove_object_from_collection(collection, preview_name)

    preview_mesh = template_mesh.copy()
    preview_mesh.name = preview_name
    preview_obj = obj.copy()
    preview_obj.data = preview_mesh
    preview_obj.name = preview_name
    _link_exclusively(preview_obj, collection)

    preview_obj.shape_key_add(name="Basis", from_mix=False)
    for name, positions in outputs:
        sk = preview_obj.shape_key_add(name=name, from_mix=False)
        sk.data.foreach_set("co", positions.reshape(-1))
        sk.value = 0.0

    preview_mesh.update()
    preview_obj.hide_render = True
    return preview_obj


def get_or_create_output_collection(obj, settings, scene):
    """
    Return the output collection, creating it if necessary and making sure it
    is linked into the scene. Also writes back the resolved name to
    settings.output_collection.
    """
    col_name = settings.output_collection.strip() or f"{obj.name}_ShapeSplits"
    settings.output_collection = col_name

    col = bpy.data.collections.get(col_name)
    if col is None:
        col = bpy.data.collections.new(col_name)
    if col not in scene.collection.children_recursive:
        scene.collection.children.link(col)

    return col


def _remove_object(o) -> None:
    mesh = o.data if o.type == 'MESH' else None
    bpy.data.objects.remove(o, do_unlink=True)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def remove_object_from_collection(col, name: str) -> None:
    """Remove the object called name if (and only if) it lives in col."""
    o = col.objects.get(name)
    if o is not None:
        _remove_object(o)


def clear_output_collection(col):
    """Remove all objects (and their mesh data) from the collection."""
    for o in list(col.objects):
        _remove_object(o)
