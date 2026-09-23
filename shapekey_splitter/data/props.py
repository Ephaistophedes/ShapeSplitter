import bpy


def _update_preview(self, context):
    """Update callback for any property that affects the live preview."""
    obj = self.id_data
    if obj is None or obj.type != 'MESH':
        return
    # Lazy import to avoid circular dependency at module load time
    from ..operators.op_preview import apply_preview
    apply_preview(obj)


class MaskRegionItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Mask", update=_update_preview)
    vertex_group: bpy.props.StringProperty(name="Vertex Group", default="", update=_update_preview)
    enabled: bpy.props.BoolProperty(name="Enabled", default=True)
    is_bilateral: bpy.props.BoolProperty(
        name="Bilateral (L+R)",
        description=(
            "Generate both _L and _R outputs, split by the center line. Disable for "
            "single-side masks like Eye_L: the painted weights alone define the region"
        ),
        default=True,
        update=_update_preview,
    )


class CenterLineSettings(bpy.types.PropertyGroup):
    # Identifier kept as "blend_falloff" so values saved by v1.0.0 carry over
    blend_falloff: bpy.props.FloatProperty(
        name="Blend Width",
        description="Full width of the left/right transition zone, centered on X=0",
        default=0.1,
        min=0.0,
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
            ('BELL',        "Bell",        "Double smoothstep (steeper S-curve with softer ends)"),
            ('EASE_IN',     "Ease In",     "Weights stay close to 50/50 near the seam and change quickly toward the edges"),
            ('EASE_OUT',    "Ease Out",    "Weights change quickly at the seam and settle softly toward the edges"),
            ('EASE_IN_OUT', "Ease In/Out", "Quadratic S-curve"),
        ],
        default='SMOOTH',
        update=_update_preview,
    )
    center_threshold: bpy.props.FloatProperty(
        name="Center Threshold",
        description=(
            "Vertices within this distance of X=0 are seam vertices: they are split "
            "exactly 50/50 between L and R and are skipped by weight mirroring"
        ),
        default=0.001,
        min=0.00001,
        soft_max=0.05,
        precision=4,
        unit='LENGTH',
        update=_update_preview,
    )
    preview_shapekey: bpy.props.StringProperty(
        name="Shape Key",
        description="Shape key to preview the split on",
        default="",
        update=_update_preview,
    )
    preview_mask: bpy.props.StringProperty(
        name="Mask",
        description="Mask to apply in preview (empty = pure centerline split)",
        default="",
        update=_update_preview,
    )
    preview_side: bpy.props.EnumProperty(
        name="Side",
        description="Which side to show",
        items=[
            ('L', "Left", "Show the left-side variant"),
            ('R', "Right", "Show the right-side variant"),
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
    # Object state to restore when preview ends
    preview_restore_index: bpy.props.IntProperty(options={'HIDDEN'})
    preview_restore_show_only: bpy.props.BoolProperty(options={'HIDDEN'})


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
