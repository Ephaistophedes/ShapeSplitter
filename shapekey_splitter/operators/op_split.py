import bpy
from ..core import splitter as splitter_mod
from ..utils.mesh_utils import unique_name


def _run_split(obj, context) -> tuple:
    """
    Core split logic shared by split_all and regenerate_all.
    Outputs with the same name as an object already in the collection replace it.
    Returns (split_objects, collection, renamed) where renamed lists outputs
    whose object name clashed with an object outside the collection.
    """
    # Edit Mode changes live in the edit-mesh until synced back to the mesh
    if obj.mode == 'EDIT':
        obj.update_from_editmode()

    settings = obj.shapekey_splitter
    col = splitter_mod.get_or_create_output_collection(obj, settings, context.scene)

    ctx = splitter_mod.SplitContext(obj, settings)
    template_mesh = splitter_mod.make_template_mesh(obj, ctx.ref_co)

    split_objects = []
    outputs = []
    renamed = []
    used_names = set()

    try:
        for kb in splitter_mod.split_candidates(obj):
            split_results = splitter_mod.split_shape_key(kb, ctx)

            for out_name, positions in split_results.items():
                final_name = unique_name(out_name, used_names)
                used_names.add(final_name)
                split_obj = splitter_mod.create_split_mesh_object(
                    obj, template_mesh, positions, final_name, col
                )
                if split_obj.name != final_name:
                    renamed.append(final_name)
                split_objects.append(split_obj)
                outputs.append((final_name, positions))

        splitter_mod.build_preview_mesh(obj, template_mesh, outputs, col)
    finally:
        bpy.data.meshes.remove(template_mesh)

    return split_objects, col, renamed


def _report_renamed(op, renamed) -> None:
    if renamed:
        op.report(
            {'WARNING'},
            f"{len(renamed)} output(s) got a numeric suffix because an object with the "
            f"same name exists outside the output collection (e.g. '{renamed[0]}')",
        )


class SHAPEKEY_OT_split_all(bpy.types.Operator):
    bl_idname = "shapekey_splitter.split_all"
    bl_label = "Split All Shape Keys"
    bl_description = (
        "Split every shape key into directional L/R and mask variants. "
        "Existing outputs with the same name are replaced"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        if not splitter_mod.split_candidates(obj):
            cls.poll_message_set("Object has no shape keys to split")
            return False
        return True

    def execute(self, context):
        obj = context.object
        split_objects, col, renamed = _run_split(obj, context)
        _report_renamed(self, renamed)
        self.report({'INFO'}, f"Generated {len(split_objects)} meshes in '{col.name}'")
        return {'FINISHED'}


class SHAPEKEY_OT_regenerate_all(bpy.types.Operator):
    bl_idname = "shapekey_splitter.regenerate_all"
    bl_label = "Regenerate All"
    bl_description = "Clear the output collection and re-run the full split"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return SHAPEKEY_OT_split_all.poll(context)

    def execute(self, context):
        obj = context.object
        settings = obj.shapekey_splitter
        col = splitter_mod.get_or_create_output_collection(obj, settings, context.scene)
        if obj.name in col.objects:
            self.report({'ERROR'}, f"'{obj.name}' is inside the output collection '{col.name}'")
            return {'CANCELLED'}
        splitter_mod.clear_output_collection(col)
        split_objects, _, renamed = _run_split(obj, context)
        _report_renamed(self, renamed)
        self.report({'INFO'}, f"Regenerated {len(split_objects)} meshes in '{col.name}'")
        return {'FINISHED'}
