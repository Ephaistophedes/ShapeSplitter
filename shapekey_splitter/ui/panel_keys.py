import bpy
from ..core.splitter import PREVIEW_KEY_NAME, is_key_selected, split_candidates


class SHAPEKEY_UL_shape_keys(bpy.types.UIList):
    """Mesh shape keys with a check mark that controls whether they are split."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        settings = context.object.shapekey_splitter
        selected = is_key_selected(settings, item.name)
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            op = row.operator(
                "shapekey_splitter.key_toggle",
                text="",
                icon='CHECKBOX_HLT' if selected else 'CHECKBOX_DEHLT',
                emboss=False,
            )
            op.name = item.name
            sub = row.row()
            sub.active = selected
            sub.label(text=item.name, icon='SHAPEKEY_DATA')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

    def filter_items(self, context, data, propname):
        key_blocks = getattr(data, propname)
        helper = bpy.types.UI_UL_list
        if self.filter_name:
            flags = helper.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, key_blocks, "name",
                reverse=self.use_filter_invert,
            )
        else:
            flags = [self.bitflag_filter_item] * len(key_blocks)

        # The reference key and the temporary preview key are never split
        ref = data.reference_key
        for i, kb in enumerate(key_blocks):
            if kb == ref or kb.name == PREVIEW_KEY_NAME:
                flags[i] = 0

        order = helper.sort_items_by_name(key_blocks, "name") if self.use_filter_sort_alpha else []
        return flags, order


def draw_shape_key_list(layout, obj):
    """Draw the shape key selection box. Returns the number of checked keys."""
    settings = obj.shapekey_splitter
    candidates = split_candidates(obj)
    n_selected = sum(1 for kb in candidates if is_key_selected(settings, kb.name))

    box = layout.box()
    box.label(text=f"Shape Keys ({n_selected}/{len(candidates)} selected)", icon='SHAPEKEY_DATA')
    box.template_list(
        "SHAPEKEY_UL_shape_keys", "",
        obj.data.shape_keys, "key_blocks",
        settings, "active_key_index",
        rows=5,
    )
    row = box.row(align=True)
    row.operator("shapekey_splitter.keys_select_all", icon='CHECKBOX_HLT')
    row.operator("shapekey_splitter.keys_clear_selection", icon='CHECKBOX_DEHLT')
    return n_selected
