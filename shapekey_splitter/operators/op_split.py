import bpy
from ..core import splitter as splitter_mod
from ..core import centerline as cl_mod
from ..utils.mesh_utils import unique_name, get_shape_key_positions


def _run_split(obj, context) -> tuple:
    """
    Core split logic shared by split_all and regenerate_all.
    Returns (split_objects, collection, count).
    """
    settings = obj.shapekey_splitter
    col = splitter_mod.get_or_create_output_collection(obj, settings)

    shape_keys = obj.data.shape_keys
    split_objects = []
    used_names = set()

    # Compute centerline weights once — identical for every shape key in the batch
    precomputed_weights = None
    basis = shape_keys.key_blocks.get("Basis")
    if basis is not None:
        cl = settings.centerline
        basis_co = get_shape_key_positions(basis)
        precomputed_weights = cl_mod.compute_centerline_weights(
            basis_co[:, 0], cl.blend_distance, cl.blend_falloff, cl.transition_type
        )

    for kb in shape_keys.key_blocks:
        if kb.name == "Basis":
            continue

        split_results = splitter_mod.split_shape_key(obj, kb.name, settings, precomputed_weights)

        for out_name, positions in split_results.items():
            final_name = unique_name(out_name, used_names)
            used_names.add(final_name)
            split_obj = splitter_mod.create_split_mesh_object(obj, positions, final_name, col)
            split_objects.append(split_obj)

    splitter_mod.build_preview_mesh(obj, split_objects, col)
    return split_objects, col, len(split_objects)


class SHAPEKEY_OT_split_all(bpy.types.Operator):
    bl_idname = "shapekey_splitter.split_all"
    bl_label = "Split All Shape Keys"
    bl_description = "Split every shape key into directional L/R and mask variants"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        sk = obj.data.shape_keys
        if sk is None or len(sk.key_blocks) <= 1:
            return False
        return True

    def execute(self, context):
        obj = context.object
        _, col, count = _run_split(obj, context)
        self.report({'INFO'}, f"Generated {count} meshes in '{col.name}'")
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
        col = splitter_mod.get_or_create_output_collection(obj, settings)
        splitter_mod.clear_output_collection(col)
        _, _, count = _run_split(obj, context)
        self.report({'INFO'}, f"Regenerated {count} meshes in '{col.name}'")
        return {'FINISHED'}
