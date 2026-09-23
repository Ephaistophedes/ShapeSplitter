if "bpy" in locals():
    import importlib
    from . import panel_main, panel_centerline, panel_masks
    importlib.reload(panel_main)
    importlib.reload(panel_centerline)
    importlib.reload(panel_masks)
else:
    from . import panel_main, panel_centerline, panel_masks

import bpy

classes = (
    panel_masks.SHAPEKEY_UL_masks,
    panel_main.SHAPEKEY_PT_main,
    panel_centerline.SHAPEKEY_PT_centerline,
    panel_masks.SHAPEKEY_PT_masks,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
