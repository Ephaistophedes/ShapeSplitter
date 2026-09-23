import bpy
from ..core import splitter as splitter_mod


def _has_candidates(context) -> bool:
    obj = context.object
    return obj is not None and obj.type == 'MESH' and bool(splitter_mod.split_candidates(obj))


class SHAPEKEY_OT_key_toggle(bpy.types.Operator):
    bl_idname = "shapekey_splitter.key_toggle"
    bl_label = "Toggle Shape Key"
    bl_description = "Include or exclude this shape key from splitting"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    name: bpy.props.StringProperty(name="Shape Key", default="")

    @classmethod
    def poll(cls, context):
        return _has_candidates(context)

    def execute(self, context):
        excluded = context.object.shapekey_splitter.excluded_keys
        idx = excluded.find(self.name)
        if idx >= 0:
            excluded.remove(idx)
        else:
            excluded.add().name = self.name
        return {'FINISHED'}


class SHAPEKEY_OT_keys_select_all(bpy.types.Operator):
    bl_idname = "shapekey_splitter.keys_select_all"
    bl_label = "Select All"
    bl_description = "Check every shape key in the list"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _has_candidates(context)

    def execute(self, context):
        context.object.shapekey_splitter.excluded_keys.clear()
        return {'FINISHED'}


class SHAPEKEY_OT_keys_clear_selection(bpy.types.Operator):
    bl_idname = "shapekey_splitter.keys_clear_selection"
    bl_label = "Clear Selection"
    bl_description = "Uncheck every shape key in the list"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _has_candidates(context)

    def execute(self, context):
        obj = context.object
        excluded = obj.shapekey_splitter.excluded_keys
        excluded.clear()
        for kb in splitter_mod.split_candidates(obj):
            excluded.add().name = kb.name
        return {'FINISHED'}
