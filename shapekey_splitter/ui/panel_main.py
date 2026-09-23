import bpy
from ..utils.mesh_utils import check_scale_applied


class SHAPEKEY_PT_main(bpy.types.Panel):
    bl_label = "Shape Key Splitter"
    bl_idname = "SHAPEKEY_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Shape Splitter"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        obj = context.object
        settings = obj.shapekey_splitter

        # --- Painting reminder ---
        info_box = layout.box()
        col = info_box.column(align=True)
        col.label(text="Enable X-Mirror when painting weights.", icon='INFO')
        col.label(text="Bilateral masks need weights on both sides.")

        layout.separator()

        # --- Scale warning ---
        if not check_scale_applied(obj):
            warn = layout.box()
            warn.alert = True
            warn.label(text="Apply scale (Ctrl+A) before splitting!", icon='ERROR')

        # --- No shape keys warning ---
        sk = obj.data.shape_keys
        has_sk = sk is not None and len(sk.key_blocks) > 1
        if not has_sk:
            layout.label(text="No shape keys found on this mesh.", icon='INFO')

        # --- Settings ---
        row = layout.row(align=True)
        row.prop(settings, "naming_separator")

        row = layout.row()
        row.prop(settings, "output_collection", text="Output Collection")

        row = layout.row()
        row.prop(settings, "include_full_lr")

        layout.separator()

        # --- Main action buttons ---
        col = layout.column(align=True)
        col.scale_y = 1.5
        col.enabled = has_sk
        col.operator("shapekey_splitter.split_all",      icon='SHADERFX')
        col.operator("shapekey_splitter.regenerate_all", icon='FILE_REFRESH')
