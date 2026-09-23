import bpy


class SHAPEKEY_UL_masks(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            row.prop(item, "name", text="", emboss=False, icon='GROUP_VERTEX')
            row.label(text=item.vertex_group)
            bilateral_icon = 'ARROW_LEFTRIGHT' if item.is_bilateral else 'FORWARD'
            row.prop(item, "is_bilateral", text="", icon=bilateral_icon, emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)


class SHAPEKEY_PT_masks(bpy.types.Panel):
    bl_label = "Mask Regions"
    bl_idname = "SHAPEKEY_PT_masks"
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

        row = layout.row()
        row.template_list(
            "SHAPEKEY_UL_masks", "",
            settings, "masks",
            settings, "active_mask_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("shapekey_splitter.mask_add",    icon='ADD',         text="")
        col.operator("shapekey_splitter.mask_remove", icon='REMOVE',      text="")
        col.separator()
        col.operator("shapekey_splitter.mask_rename", icon='GREASEPENCIL', text="")

        layout.operator("shapekey_splitter.add_default_masks", icon='ADD')

        # Selected mask detail panel
        idx = settings.active_mask_index
        if 0 <= idx < len(settings.masks):
            mask = settings.masks[idx]
            box = layout.box()
            box.label(text=f'Selected: "{mask.name}"', icon='GROUP_VERTEX')

            box.prop_search(mask, "vertex_group", obj, "vertex_groups", text="Vertex Group")
            box.prop(mask, "is_bilateral")

            if mask.is_bilateral:
                row2 = box.row(align=True)
                op = row2.operator(
                    "shapekey_splitter.mirror_weights",
                    text="Mirror Weights L\u2192R",
                    icon='MOD_MIRROR',
                )
                op.vertex_group = mask.vertex_group
            else:
                box.label(text="Single-side: paint the region directly", icon='INFO')
            if mask.vertex_group not in obj.vertex_groups:
                box.label(text=f"Vertex group '{mask.vertex_group}' not found", icon='ERROR')

            is_editing = context.mode == 'PAINT_WEIGHT'
            edit_row = box.row()
            edit_row.alert = is_editing
            op2 = edit_row.operator(
                "shapekey_splitter.select_vertices_for_paint",
                text="Exit Edit Mode" if is_editing else "Edit Mask",
                icon='WPAINT_HLT',
            )
            op2.vertex_group = mask.vertex_group
