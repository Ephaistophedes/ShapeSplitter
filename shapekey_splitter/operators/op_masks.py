import bpy

DEFAULT_MASKS = [
    {"name": "Eyes",  "vertex_group": "eyes",  "is_bilateral": True},
    {"name": "Mouth", "vertex_group": "mouth", "is_bilateral": True},
]


class SHAPEKEY_OT_add_default_masks(bpy.types.Operator):
    bl_idname = "shapekey_splitter.add_default_masks"
    bl_label = "Add Default Masks"
    bl_description = "Add the default mask regions (Eyes, Mouth) and their vertex groups if not already present"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter

        for default in DEFAULT_MASKS:
            if not any(m.name == default["name"] for m in settings.masks):
                item = settings.masks.add()
                item.name = default["name"]
                item.vertex_group = default["vertex_group"]
                item.is_bilateral = default["is_bilateral"]

                if default["vertex_group"] not in obj.vertex_groups:
                    obj.vertex_groups.new(name=default["vertex_group"])

        return {'FINISHED'}


class SHAPEKEY_OT_mask_add(bpy.types.Operator):
    bl_idname = "shapekey_splitter.mask_add"
    bl_label = "Add Mask Region"
    bl_description = "Add a new mask region and its vertex group"
    bl_options = {'REGISTER', 'UNDO'}

    name: bpy.props.StringProperty(name="Name", default="New Mask")

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter

        name = self.name.strip()
        if not name:
            self.report({'WARNING'}, "Mask name cannot be empty")
            return {'CANCELLED'}

        item = settings.masks.add()
        item.name = name
        item.is_bilateral = True

        vg_name = name.lower().replace(' ', '_')
        if vg_name not in obj.vertex_groups:
            vg_name = obj.vertex_groups.new(name=vg_name).name
        item.vertex_group = vg_name

        settings.active_mask_index = len(settings.masks) - 1
        return {'FINISHED'}


class SHAPEKEY_OT_mask_remove(bpy.types.Operator):
    bl_idname = "shapekey_splitter.mask_remove"
    bl_label = "Remove Mask Region"
    bl_description = "Remove the selected mask region (vertex group is kept)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        return len(obj.shapekey_splitter.masks) > 0

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter
        idx = settings.active_mask_index

        if idx >= len(settings.masks):
            return {'CANCELLED'}

        settings.masks.remove(idx)
        settings.active_mask_index = max(0, min(idx, len(settings.masks) - 1))
        return {'FINISHED'}


class SHAPEKEY_OT_mask_rename(bpy.types.Operator):
    bl_idname = "shapekey_splitter.mask_rename"
    bl_label = "Rename Mask Region"
    bl_description = "Rename the mask region and its associated vertex group"
    bl_options = {'REGISTER', 'UNDO'}

    new_name: bpy.props.StringProperty(name="New Name", default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        return len(obj.shapekey_splitter.masks) > 0

    def invoke(self, context, event):
        settings = context.object.shapekey_splitter
        idx = settings.active_mask_index
        if idx < len(settings.masks):
            self.new_name = settings.masks[idx].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter
        idx = settings.active_mask_index

        if idx >= len(settings.masks):
            return {'CANCELLED'}

        new_name = self.new_name.strip()
        if not new_name:
            self.report({'WARNING'}, "Mask name cannot be empty")
            return {'CANCELLED'}

        mask = settings.masks[idx]
        old_vg_name = mask.vertex_group
        new_vg_name = new_name.lower().replace(' ', '_')

        vg = obj.vertex_groups.get(old_vg_name)
        if vg is not None and vg.name != new_vg_name:
            if new_vg_name in obj.vertex_groups:
                self.report(
                    {'ERROR'},
                    f"Vertex group '{new_vg_name}' already exists — rename or remove it first",
                )
                return {'CANCELLED'}
            vg.name = new_vg_name

        cl = settings.centerline
        if cl.preview_mask == mask.name:
            cl.preview_mask = new_name

        mask.name = new_name
        mask.vertex_group = vg.name if vg is not None else new_vg_name
        return {'FINISHED'}


class SHAPEKEY_OT_select_vertices_for_paint(bpy.types.Operator):
    bl_idname = "shapekey_splitter.select_vertices_for_paint"
    bl_label = "Edit Mask"
    bl_description = "Toggle Weight Paint mode for this mask's vertex group"
    bl_options = {'REGISTER', 'UNDO'}

    vertex_group: bpy.props.StringProperty(name="Vertex Group", default="")

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.object

        if context.mode == 'PAINT_WEIGHT':
            bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}

        if self.vertex_group and self.vertex_group in obj.vertex_groups:
            obj.vertex_groups.active = obj.vertex_groups[self.vertex_group]

        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}
