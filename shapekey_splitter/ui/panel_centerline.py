import bpy


class SHAPEKEY_PT_centerline(bpy.types.Panel):
    bl_label = "Center Line Settings"
    bl_idname = "SHAPEKEY_PT_centerline"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Shape Splitter"
    bl_parent_id = "SHAPEKEY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        obj = context.object
        settings = obj.shapekey_splitter
        cl = settings.centerline

        layout.prop(cl, "transition_type")
        layout.prop(cl, "blend_distance")
        layout.prop(cl, "blend_falloff")
        layout.prop(cl, "center_threshold")

        layout.separator()

        # --- Preview section ---
        layout.label(text="Preview:", icon='HIDE_OFF')

        sk_data = obj.data.shape_keys
        if sk_data is not None:
            layout.prop_search(cl, "preview_shapekey", sk_data, "key_blocks", text="Shape Key")
        else:
            layout.label(text="No shape keys on this mesh", icon='INFO')

        # Mask selector
        if settings.masks:
            layout.prop_search(cl, "preview_mask", settings, "masks", text="Mask")
            if cl.preview_mask:
                active_mask = next(
                    (m for m in settings.masks if m.name == cl.preview_mask), None
                )
                if active_mask and active_mask.is_bilateral:
                    row = layout.row()
                    row.prop(cl, "preview_side", expand=True)

        row = layout.row(align=True)
        if cl.preview_active:
            row.alert = True
            row.operator("shapekey_splitter.preview_stop", icon='PAUSE', text="Exit Preview")
        else:
            row.operator("shapekey_splitter.preview_start", icon='PLAY', text="Enter Preview Mode")

        layout.separator()
        layout.operator(
            "shapekey_splitter.mirror_weights",
            text="Mirror Weights L\u2192R (Global)",
            icon='MOD_MIRROR',
        )
