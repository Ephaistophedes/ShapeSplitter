if "bpy" in locals():
    import importlib
    from . import props
    importlib.reload(props)
else:
    from . import props

import bpy

# PropertyGroups must be registered before any class that references them
classes = (
    props.MaskRegionItem,
    props.ShapeKeyNameItem,
    props.CenterLineSettings,
    props.ShapeKeySplitterSettings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.shapekey_splitter = bpy.props.PointerProperty(
        type=props.ShapeKeySplitterSettings
    )


def unregister():
    del bpy.types.Object.shapekey_splitter
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
