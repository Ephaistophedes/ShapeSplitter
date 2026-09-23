import bpy


def _update_preview(self, context):
    """Update callback for any property that affects the live preview."""
    if not self.preview_active:
        return
    obj = context.object
    if obj is None or obj.type != 'MESH':
        return
    # Lazy import to avoid circular dependency at module load time
    from ..operators.op_preview import apply_preview
    apply_preview(obj, self.preview_shapekey, self.preview_strength, obj.shapekey_splitter)


def _update_preview_shapekey(self, context):
    """Called when the user picks a different shape key while preview is active."""
    if not self.preview_active:
        return
    obj = context.object
    if obj is None or obj.type != 'MESH':
        return
    from ..operators.op_preview import switch_preview_shapekey
    switch_preview_shapekey(obj, self.preview_shapekey, obj.shapekey_splitter)


class MaskRegionItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Mask")
    vertex_group: bpy.props.StringProperty(name="Vertex Group", default="")
    enabled: bpy.props.BoolProperty(name="Enabled", default=True)
    is_bilateral: bpy.props.BoolProperty(
        name="Bilateral (L+R)",
        description="Generate both _L and _R outputs. Disable for single-side masks like Eye_L",
        default=True,
    )


class CenterLineSettings(bpy.types.PropertyGroup):
    blend_distance: bpy.props.FloatProperty(
        name="Blend Start",
        description="World-space distance from X=0 where blending starts",
        default=0.05,
        min=0.0,
        soft_max=1.0,
        unit='LENGTH',
        update=_update_preview,
    )
    blend_falloff: bpy.props.FloatProperty(
        name="Blend Falloff",
        description="World-space distance over which the blend transitions",
        default=0.1,
        min=0.001,
        soft_max=1.0,
        unit='LENGTH',
        update=_update_preview,
    )
    transition_type: bpy.props.EnumProperty(
        name="Transition Type",
        description="Curve shape for the left/right blend transition",
        items=[
            ('LINEAR',      "Linear",      "Linear interpolation"),
            ('SMOOTH',      "Smooth",      "Smoothstep (cubic S-curve)"),
            ('BELL',        "Bell",        "Double smoothstep (very soft S-curve)"),
            ('EASE_IN',     "Ease In",     "Starts slow, accelerates"),
            ('EASE_OUT',    "Ease Out",    "Starts fast, decelerates"),
            ('EASE_IN_OUT', "Ease In/Out", "Standard cubic ease"),
        ],
        default='SMOOTH',
        update=_update_preview,
    )
    center_threshold: bpy.props.FloatProperty(
        name="Center Threshold",
        description="Vertices within this distance of X=0 are treated as center verts (weight capped at 0.5)",
        default=0.001,
        min=0.00001,
        soft_max=0.05,
        precision=4,
        unit='LENGTH',
        update=_update_preview,
    )
    preview_active: bpy.props.BoolProperty(
        name="Preview Active",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    preview_shapekey: bpy.props.StringProperty(
        name="Shape Key",
        description="Shape key to preview the centerline split on",
        default="",
        update=_update_preview_shapekey,
    )
    preview_mask: bpy.props.StringProperty(
        name="Mask",
        description="Mask to apply in preview (empty = pure centerline L split)",
        default="",
        update=_update_preview,
    )
    preview_side: bpy.props.EnumProperty(
        name="Side",
        description="Which side to show for bilateral masks",
        items=[
            ('L', "Left", "Show left-side masked variant"),
            ('R', "Right", "Show right-side masked variant"),
        ],
        default='L',
        update=_update_preview,
    )
    preview_strength: bpy.props.FloatProperty(
        name="Strength",
        description="Preview blend strength",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=_update_preview,
    )


class ShapeKeySplitterSettings(bpy.types.PropertyGroup):
    masks: bpy.props.CollectionProperty(type=MaskRegionItem)
    active_mask_index: bpy.props.IntProperty(default=0, min=0)
    centerline: bpy.props.PointerProperty(type=CenterLineSettings)
    naming_separator: bpy.props.StringProperty(
        name="Separator",
        description="Character(s) between shape key name and L/R suffix",
        default="_",
        maxlen=4,
    )
    keep_original: bpy.props.BoolProperty(
        name="Keep Original",
        description="Keep the original shape key after splitting",
        default=True,
    )
    include_full_lr: bpy.props.BoolProperty(
        name="Include Full L/R",
        description="Also output the unmasked centerline L and R splits (in addition to masked variants)",
        default=False,
    )
    output_collection: bpy.props.StringProperty(
        name="Output Collection",
        description="Name of the collection that receives split mesh objects",
        default="",
    )
