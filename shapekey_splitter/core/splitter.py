"""
Shape key splitting algorithm and output mesh/collection management.
"""

import numpy as np
import bpy

from . import centerline as cl_mod
from ..utils.mesh_utils import get_shape_key_positions, get_vertex_group_weights


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clone_obj_into_collection(obj, name: str, collection) -> tuple:
    """
    Copy obj+mesh, strip all shape keys, link exclusively to collection.
    Returns (new_obj, new_mesh).
    """
    new_mesh = obj.data.copy()
    new_obj = obj.copy()
    new_obj.data = new_mesh
    new_obj.name = name
    new_mesh.name = name

    # Remove shape keys last→first so Basis is removed last,
    # preventing Blender from baking deltas into geometry when Basis is promoted
    if new_mesh.shape_keys is not None:
        while new_mesh.shape_keys is not None:
            new_obj.shape_key_remove(new_mesh.shape_keys.key_blocks[-1])

    collection.objects.link(new_obj)
    for coll in list(new_obj.users_collection):
        if coll != collection:
            coll.objects.unlink(new_obj)

    return new_obj, new_mesh


# ---------------------------------------------------------------------------
# Core split computation
# ---------------------------------------------------------------------------

def split_shape_key(obj, sk_name: str, settings, precomputed_weights=None) -> dict:
    """
    Compute all split variants for one shape key.

    Returns:
        {output_name: (N, 3) float32 positions array}

    Output includes:
      - Always: {sk_name}{sep}L  and  {sk_name}{sep}R  (pure centerline split)
      - Per active bilateral mask:  {sk_name}_{mask_name}{sep}L  and  ..._R
      - Per active single-side mask: {sk_name}_{mask_name}  (one output only)

    precomputed_weights: optional (weight_L, weight_R) tuple from a prior call to
        compute_centerline_weights — pass when splitting many shape keys in a loop
        to avoid recomputing identical weights for each key.
    """
    mesh = obj.data
    shape_keys = mesh.shape_keys
    if shape_keys is None:
        return {}

    basis = shape_keys.key_blocks.get("Basis")
    sk = shape_keys.key_blocks.get(sk_name)
    if basis is None or sk is None:
        return {}

    basis_co = get_shape_key_positions(basis)   # (N, 3)
    sk_co = get_shape_key_positions(sk)         # (N, 3)
    delta = sk_co - basis_co                    # (N, 3)

    if precomputed_weights is not None:
        weight_L, weight_R = precomputed_weights
    else:
        cl = settings.centerline
        weight_L, weight_R = cl_mod.compute_centerline_weights(
            basis_co[:, 0],
            cl.blend_distance,
            cl.blend_falloff,
            cl.transition_type,
        )

    sep = settings.naming_separator
    results = {}

    # --- Base L/R split (no mask) — optional ---
    if settings.include_full_lr:
        results[f"{sk_name}{sep}L"] = (basis_co + delta * weight_L[:, np.newaxis]).astype(np.float32)
        results[f"{sk_name}{sep}R"] = (basis_co + delta * weight_R[:, np.newaxis]).astype(np.float32)

    # --- Mask variants ---
    active_masks = [m for m in settings.masks if m.enabled]
    for mask in active_masks:
        mask_w = get_vertex_group_weights(obj, mask.vertex_group)  # (N,)
        mask_name = mask.name.lower().replace(" ", "_")

        if mask.is_bilateral:
            # Multiply user mask by centerline weights so the blend transition
            # is applied to the masked region, not just a hard zero at the axis.
            results[f"{sk_name}_{mask_name}{sep}L"] = (
                basis_co + delta * (mask_w * weight_L)[:, np.newaxis]
            ).astype(np.float32)
            results[f"{sk_name}_{mask_name}{sep}R"] = (
                basis_co + delta * (mask_w * weight_R)[:, np.newaxis]
            ).astype(np.float32)
        else:
            # Single-side: user mask gated by left centerline weight.
            results[f"{sk_name}_{mask_name}"] = (
                basis_co + delta * (mask_w * weight_L)[:, np.newaxis]
            ).astype(np.float32)

    return results


# ---------------------------------------------------------------------------
# Output mesh / collection helpers
# ---------------------------------------------------------------------------

def create_split_mesh_object(obj, positions: np.ndarray, name: str, collection) -> object:
    """
    Duplicate the source object, bake split positions into vertices, link to collection.
    The duplicate has no shape keys — the deformation is frozen into geometry.
    """
    new_obj, new_mesh = _clone_obj_into_collection(obj, name, collection)
    new_mesh.vertices.foreach_set("co", positions.reshape(-1))
    new_mesh.update()
    new_obj.hide_render = True
    return new_obj


def build_preview_mesh(obj, split_objects: list, collection) -> object:
    """
    Build {obj.name}_Preview: a full duplicate of the source mesh with every
    split result added as a shape key (all at value 0.0 by default).

    Must be called AFTER all split meshes have been generated.
    """
    preview_name = f"{obj.name}_Preview"

    # Remove stale preview if present
    existing = bpy.data.objects.get(preview_name)
    if existing is not None:
        mesh = existing.data
        bpy.data.objects.remove(existing, do_unlink=True)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    preview_obj, preview_mesh = _clone_obj_into_collection(obj, preview_name, collection)

    # Add Basis
    preview_obj.shape_key_add(name="Basis", from_mix=False)

    n = len(preview_mesh.vertices)

    # Add each split mesh as a shape key
    for split_obj in split_objects:
        sk = preview_obj.shape_key_add(name=split_obj.name, from_mix=False)
        split_co = np.empty(n * 3, dtype=np.float32)
        split_obj.data.vertices.foreach_get("co", split_co)
        sk.data.foreach_set("co", split_co)
        sk.value = 0.0

    preview_mesh.update()
    preview_obj.hide_render = True
    return preview_obj


def get_or_create_output_collection(obj, settings):
    """
    Return the output collection, creating and linking it if necessary.
    Also writes back the resolved name to settings.output_collection.
    """
    col_name = settings.output_collection.strip() or f"{obj.name}_ShapeSplits"
    settings.output_collection = col_name

    col = bpy.data.collections.get(col_name)
    if col is None:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    return col


def clear_output_collection(col):
    """Remove all objects (and their mesh data) from the collection."""
    for o in list(col.objects):
        mesh = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
