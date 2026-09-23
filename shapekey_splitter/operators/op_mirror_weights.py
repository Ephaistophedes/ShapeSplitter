import bpy
from ..core.weights import mirror_weights_left_to_right


class SHAPEKEY_OT_mirror_weights(bpy.types.Operator):
    bl_idname = "shapekey_splitter.mirror_weights"
    bl_label = "Mirror Weights L\u2192R"
    bl_description = (
        "Copy vertex group weights from the left side (X<0) to matching right-side vertices"
    )
    bl_options = {'REGISTER', 'UNDO'}

    vertex_group: bpy.props.StringProperty(
        name="Vertex Group",
        description="Specific vertex group to mirror. Leave empty to mirror all active masks",
        default="",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (
            obj is not None
            and obj.type == 'MESH'
            and context.mode in ('OBJECT', 'PAINT_WEIGHT')
        )

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter
        cl = settings.centerline

        if self.vertex_group:
            vg_names = [self.vertex_group]
        else:
            vg_names = [
                m.vertex_group
                for m in settings.masks
                if m.enabled and m.vertex_group
            ]

        if not vg_names:
            self.report({'WARNING'}, "No vertex groups to mirror")
            return {'CANCELLED'}

        total = 0
        for vg_name in vg_names:
            count, warnings = mirror_weights_left_to_right(obj, vg_name, cl.center_threshold)
            total += count
            for w in warnings:
                self.report({'WARNING'}, w)

        self.report(
            {'INFO'},
            f"Mirrored {total} vertices across {len(vg_names)} group(s)",
        )
        return {'FINISHED'}
