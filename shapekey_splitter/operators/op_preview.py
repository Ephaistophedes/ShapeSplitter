"""
Interactive preview of the centerline split on a single shape key.

preview_active is SKIP_SAVE so it never persists across file reloads.
The backup dict is module-level (session memory only).
"""

import bpy
import numpy as np

from ..core import centerline as cl_mod
from ..utils.mesh_utils import get_shape_key_positions, get_vertex_group_weights

# {(obj_name, sk_name): (flat (N*3,) float32 original positions, original value)}
_preview_backup: dict = {}


def _save_backup(obj, sk) -> None:
    """Snapshot shape key positions and value into _preview_backup."""
    backup = np.empty(len(sk.data) * 3, dtype=np.float32)
    sk.data.foreach_get("co", backup)
    _preview_backup[(obj.name, sk.name)] = (backup, sk.value)


def apply_preview(obj, sk_name: str, strength: float, settings) -> None:
    """
    Write a preview split into shape key data directly.
    Only the L-weighted version is shown (for simplicity in preview).
    Restores nothing — call stop_preview to undo.
    """
    if not sk_name:
        return

    mesh = obj.data
    shape_keys = mesh.shape_keys
    if shape_keys is None:
        return

    sk = shape_keys.key_blocks.get(sk_name)
    basis = shape_keys.key_blocks.get("Basis")
    if sk is None or basis is None:
        return

    backup_key = (obj.name, sk_name)
    if backup_key not in _preview_backup:
        return  # not started, do nothing

    basis_co = get_shape_key_positions(basis)       # (N, 3)
    orig_co = _preview_backup[backup_key][0].reshape(-1, 3)
    delta = orig_co - basis_co

    cl = settings.centerline
    x_coords = basis_co[:, 0]

    weight_L, weight_R = cl_mod.compute_centerline_weights(
        x_coords,
        cl.blend_distance,
        cl.blend_falloff,
        cl.transition_type,
    )

    # Determine final per-vertex weight
    final_weight = weight_L  # default: pure L split
    if cl.preview_mask:
        mask = next(
            (m for m in settings.masks if m.name == cl.preview_mask and m.enabled),
            None,
        )
        if mask is not None:
            mask_w = get_vertex_group_weights(obj, mask.vertex_group)
            if mask.is_bilateral and cl.preview_side == 'R':
                final_weight = mask_w * weight_R
            else:
                final_weight = mask_w * weight_L

    preview_co = basis_co + delta * (final_weight[:, np.newaxis] * strength)
    sk.data.foreach_set("co", preview_co.reshape(-1).astype(np.float32))
    mesh.update()


def switch_preview_shapekey(obj, new_sk_name: str, settings) -> None:
    """
    While preview is active, restore the currently previewed shape key and
    switch to new_sk_name. Called when the user picks a different shape key
    in the UI during an active preview session.
    """
    mesh = obj.data
    if mesh.shape_keys is None:
        return

    # Restore any shape key currently being previewed for this object
    for key in list(_preview_backup.keys()):
        obj_name, old_sk_name = key
        if obj_name != obj.name:
            continue
        sk = mesh.shape_keys.key_blocks.get(old_sk_name)
        if sk is not None:
            positions, orig_value = _preview_backup[key]
            sk.data.foreach_set("co", positions)
            sk.value = orig_value
            mesh.update()
        _preview_backup.pop(key, None)

    if not new_sk_name:
        return

    sk = mesh.shape_keys.key_blocks.get(new_sk_name)
    if sk is None:
        return

    _save_backup(obj, sk)
    sk.value = 1.0
    apply_preview(obj, new_sk_name, settings.centerline.preview_strength, settings)


class SHAPEKEY_OT_preview_start(bpy.types.Operator):
    bl_idname = "shapekey_splitter.preview_start"
    bl_label = "Enter Preview Mode"
    bl_description = "Preview the centerline L-split on the selected shape key"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        if obj.data.shape_keys is None:
            return False
        return not obj.shapekey_splitter.centerline.preview_active

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter
        cl = settings.centerline

        if not cl.preview_shapekey:
            self.report({'WARNING'}, "No shape key selected for preview")
            return {'CANCELLED'}

        sk = obj.data.shape_keys.key_blocks.get(cl.preview_shapekey)
        if sk is None:
            self.report({'WARNING'}, f"Shape key '{cl.preview_shapekey}' not found")
            return {'CANCELLED'}

        _save_backup(obj, sk)
        cl.preview_active = True
        sk.value = 1.0
        apply_preview(obj, cl.preview_shapekey, cl.preview_strength, settings)
        return {'FINISHED'}


class SHAPEKEY_OT_preview_stop(bpy.types.Operator):
    bl_idname = "shapekey_splitter.preview_stop"
    bl_label = "Exit Preview Mode"
    bl_description = "Restore the original shape key and exit preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        if obj.data.shape_keys is None:
            return False
        return obj.shapekey_splitter.centerline.preview_active

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter
        cl = settings.centerline

        backup_key = (obj.name, cl.preview_shapekey)
        if backup_key in _preview_backup:
            mesh = obj.data
            sk = mesh.shape_keys.key_blocks.get(cl.preview_shapekey) if mesh.shape_keys else None
            if sk is not None:
                positions, orig_value = _preview_backup[backup_key]
                sk.data.foreach_set("co", positions)
                sk.value = orig_value
                mesh.update()
            del _preview_backup[backup_key]

        cl.preview_active = False
        return {'FINISHED'}
