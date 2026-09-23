"""
Interactive preview of the split on a single shape key.

The preview is written into a temporary shape key (PREVIEW_KEY_NAME) that is
shown solo via "Shape Key Lock" (show_only_shape_key). The source shape keys are
never modified. Whether preview is active is derived from the existence of that
key, so the state stays correct across undo, file save/reload, object renames
and add-on reloads.
"""

import bpy
import numpy as np

from ..core import splitter as splitter_mod
from ..core.splitter import PREVIEW_KEY_NAME


def get_preview_key(obj):
    shape_keys = obj.data.shape_keys if obj is not None and obj.type == 'MESH' else None
    if shape_keys is None:
        return None
    return shape_keys.key_blocks.get(PREVIEW_KEY_NAME)


def is_preview_active(obj) -> bool:
    return get_preview_key(obj) is not None


def find_preview_mask(settings):
    """The mask selected for preview (enabled or not), or None."""
    name = settings.centerline.preview_mask
    if not name:
        return None
    return next((m for m in settings.masks if m.name == name), None)


def apply_preview(obj) -> None:
    """Recompute the preview key from the current settings."""
    pk = get_preview_key(obj)
    if pk is None:
        return

    shape_keys = obj.data.shape_keys
    settings = obj.shapekey_splitter
    cl = settings.centerline
    ref = shape_keys.reference_key

    mask = find_preview_mask(settings)
    ctx = splitter_mod.SplitContext(obj, settings, masks=[mask] if mask else [])

    sk = shape_keys.key_blocks.get(cl.preview_shapekey)
    if sk is None or sk == pk or sk == ref:
        positions = ctx.ref_co
    else:
        side_w = ctx.weight_R if cl.preview_side == 'R' else ctx.weight_L
        if ctx.masks:
            mask_w = ctx.masks[0][1]
            final_weight = mask_w * side_w if mask.is_bilateral else mask_w
        else:
            final_weight = side_w

        delta = splitter_mod.shape_key_delta(sk)
        positions = ctx.ref_co + delta * (final_weight[:, np.newaxis] * cl.preview_strength)

    pk.relative_key = ref
    pk.data.foreach_set("co", positions.reshape(-1).astype(np.float32))
    pk.value = 1.0
    obj.data.update()


def _preview_poll(cls, context, want_active: bool) -> bool:
    obj = context.object
    if obj is None or obj.type != 'MESH':
        return False
    if obj.data.shape_keys is None:
        cls.poll_message_set("Object has no shape keys")
        return False
    if context.mode not in ('OBJECT', 'PAINT_WEIGHT'):
        cls.poll_message_set("Preview is only available in Object and Weight Paint mode")
        return False
    return is_preview_active(obj) == want_active


class SHAPEKEY_OT_preview_start(bpy.types.Operator):
    bl_idname = "shapekey_splitter.preview_start"
    bl_label = "Enter Preview Mode"
    bl_description = (
        "Preview the split on the selected shape key. The result is shown on a "
        f"temporary '{PREVIEW_KEY_NAME}' shape key; the original is not modified"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _preview_poll(cls, context, want_active=False)

    def execute(self, context):
        obj = context.object
        cl = obj.shapekey_splitter.centerline
        shape_keys = obj.data.shape_keys

        if not cl.preview_shapekey:
            self.report({'WARNING'}, "No shape key selected for preview")
            return {'CANCELLED'}

        sk = shape_keys.key_blocks.get(cl.preview_shapekey)
        if sk is None or sk == shape_keys.reference_key:
            self.report({'WARNING'}, f"'{cl.preview_shapekey}' is not a shape key that can be split")
            return {'CANCELLED'}

        cl.preview_restore_index = obj.active_shape_key_index
        cl.preview_restore_show_only = obj.show_only_shape_key

        pk = obj.shape_key_add(name=PREVIEW_KEY_NAME, from_mix=False)
        obj.active_shape_key_index = shape_keys.key_blocks.find(pk.name)
        obj.show_only_shape_key = True
        apply_preview(obj)
        return {'FINISHED'}


class SHAPEKEY_OT_preview_stop(bpy.types.Operator):
    bl_idname = "shapekey_splitter.preview_stop"
    bl_label = "Exit Preview Mode"
    bl_description = f"Remove the temporary '{PREVIEW_KEY_NAME}' shape key and exit preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _preview_poll(cls, context, want_active=True)

    def execute(self, context):
        obj = context.object
        cl = obj.shapekey_splitter.centerline

        obj.shape_key_remove(get_preview_key(obj))

        n_keys = len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0
        obj.active_shape_key_index = max(0, min(cl.preview_restore_index, n_keys - 1))
        obj.show_only_shape_key = cl.preview_restore_show_only
        obj.data.update()
        return {'FINISHED'}
