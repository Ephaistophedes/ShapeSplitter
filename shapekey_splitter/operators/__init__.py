if "bpy" in locals():
    import importlib
    from . import op_split, op_mirror_weights, op_preview, op_masks
    importlib.reload(op_split)
    importlib.reload(op_mirror_weights)
    importlib.reload(op_preview)
    importlib.reload(op_masks)
else:
    from . import op_split, op_mirror_weights, op_preview, op_masks

import bpy

classes = (
    op_split.SHAPEKEY_OT_split_all,
    op_split.SHAPEKEY_OT_regenerate_all,
    op_mirror_weights.SHAPEKEY_OT_mirror_weights,
    op_preview.SHAPEKEY_OT_preview_start,
    op_preview.SHAPEKEY_OT_preview_stop,
    op_masks.SHAPEKEY_OT_add_default_masks,
    op_masks.SHAPEKEY_OT_mask_add,
    op_masks.SHAPEKEY_OT_mask_remove,
    op_masks.SHAPEKEY_OT_mask_rename,
    op_masks.SHAPEKEY_OT_select_vertices_for_paint,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
