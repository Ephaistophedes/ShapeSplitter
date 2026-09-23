"""
Headless tests for the Shape Key Splitter add-on.

Run with either:
    blender -b --factory-startup --python tests/run_tests.py
    python tests/run_tests.py          # with the `bpy` module from PyPI installed

Exits with a non-zero status if any test fails.
"""

import os
import sys
import tempfile
import time
import unittest

import bpy
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import shapekey_splitter  # noqa: E402
from shapekey_splitter.core import centerline, weights, splitter  # noqa: E402
from shapekey_splitter.operators.op_preview import is_preview_active  # noqa: E402
from shapekey_splitter.utils.mesh_utils import get_vertex_group_weights  # noqa: E402

CURVES = ('LINEAR', 'SMOOTH', 'BELL', 'EASE_IN', 'EASE_OUT', 'EASE_IN_OUT')
TEST_SCENE = os.path.join(REPO, "test_scenes", "Test_Scene.blend")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_grid(name="Face", n=21, half=0.2):
    """Flat symmetric grid in the XY plane with a 'Smile' key that lifts every vertex by 1 in Z."""
    xs = np.linspace(-half, half, n)
    verts = [(x, y, 0.0) for y in np.linspace(-half, half, n) for x in xs]
    faces = [
        (r * n + c, r * n + c + 1, (r + 1) * n + c + 1, (r + 1) * n + c)
        for r in range(n - 1) for c in range(n - 1)
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    obj.shape_key_add(name="Basis", from_mix=False)
    smile = obj.shape_key_add(name="Smile", from_mix=False)
    co = np.empty(len(mesh.vertices) * 3, np.float32)
    smile.data.foreach_get("co", co)
    co = co.reshape(-1, 3)
    co[:, 2] += 1.0
    smile.data.foreach_set("co", co.reshape(-1))
    return obj


def vertex_x(obj):
    co = np.empty(len(obj.data.vertices) * 3, np.float32)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)[:, 0]


def object_z(obj):
    co = np.empty(len(obj.data.vertices) * 3, np.float32)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)[:, 2]


def key_co(kb):
    co = np.empty(len(kb.data) * 3, np.float32)
    kb.data.foreach_get("co", co)
    return co.reshape(-1, 3)


def add_mask(obj, name, vg_name, weights_by_index, bilateral=True):
    vg = obj.vertex_groups.get(vg_name) or obj.vertex_groups.new(name=vg_name)
    for i, w in weights_by_index.items():
        vg.add([i], w, 'REPLACE')
    m = obj.shapekey_splitter.masks.add()
    m.name, m.vertex_group, m.is_bilateral = name, vg_name, bilateral
    return m


def run_op(op, obj, **kwargs):
    with bpy.context.temp_override(object=obj, active_object=obj):
        return op(**kwargs)


def outputs(obj):
    col = bpy.data.collections[obj.shapekey_splitter.output_collection]
    return {o.name: o for o in col.objects}


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------

class TestCurves(unittest.TestCase):
    def test_curves_are_point_symmetric_and_bounded(self):
        t = np.linspace(0.0, 1.0, 101, dtype=np.float32)
        for c in CURVES:
            f = weights.apply_curve(t, c)
            self.assertAlmostEqual(float(f[0]), 0.0, places=5, msg=c)
            self.assertAlmostEqual(float(f[-1]), 1.0, places=5, msg=c)
            np.testing.assert_allclose(f[::-1], 1.0 - f, atol=1e-5, err_msg=c)
            self.assertTrue(np.all(np.diff(f) >= -1e-6), msg=f"{c} not monotonic")

    def test_centerline_is_centered_and_mirrored(self):
        x = np.linspace(-0.3, 0.3, 601, dtype=np.float32)   # symmetric samples
        for c in CURVES:
            for width in (0.02, 0.1, 0.25, 0.5):
                wl, wr = centerline.compute_centerline_weights(x, width, c, 0.0)
                np.testing.assert_allclose(wl + wr, 1.0, atol=1e-6)
                np.testing.assert_allclose(wr, wl[::-1], atol=1e-5, err_msg=f"{c} {width}")
                self.assertAlmostEqual(float(wl[300]), 0.5, places=5)   # x == 0
                self.assertTrue(np.all(wl[x <= -width / 2] == 1.0))
                self.assertTrue(np.all(wl[x >= width / 2] == 0.0))

    def test_center_threshold_forces_even_split(self):
        x = np.array([-0.0009, 0.0, 0.0009, 0.002], dtype=np.float32)
        wl, _ = centerline.compute_centerline_weights(x, 0.0, 'LINEAR', 0.001)
        np.testing.assert_array_equal(wl, [0.5, 0.5, 0.5, 0.0])

    def test_zero_width_is_hard_split(self):
        x = np.array([-0.5, -0.01, 0.01, 0.5], dtype=np.float32)
        wl, wr = centerline.compute_centerline_weights(x, 0.0, 'SMOOTH', 0.0)
        np.testing.assert_array_equal(wl, [1, 1, 0, 0])
        np.testing.assert_array_equal(wr, [0, 0, 1, 1])


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

class TestSplit(unittest.TestCase):
    def setUp(self):
        reset_scene()
        self.obj = make_grid()
        s = self.obj.shapekey_splitter
        s.include_full_lr = True
        s.centerline.blend_falloff = 0.1
        s.centerline.transition_type = 'LINEAR'

    def split(self):
        self.assertEqual(run_op(bpy.ops.shapekey_splitter.split_all, self.obj), {'FINISHED'})
        return outputs(self.obj)

    def test_full_lr_sums_to_original(self):
        out = self.split()
        z = object_z(out["Smile_L"]) + object_z(out["Smile_R"])
        np.testing.assert_allclose(z, 1.0, atol=1e-6)

    def test_right_side_single_mask_is_not_empty(self):
        x = vertex_x(self.obj)
        right = {int(i): 1.0 for i in np.where(x > 0.1)[0]}
        add_mask(self.obj, "Eye_R", "eye_r", right, bilateral=False)
        z = object_z(self.split()["Smile_eye_r"])
        np.testing.assert_allclose(z[x > 0.1], 1.0)
        np.testing.assert_allclose(z[x <= 0.1], 0.0)

    def test_bilateral_mask_halves_sum_to_mask(self):
        mask = {i: 0.5 for i in range(len(self.obj.data.vertices))}
        add_mask(self.obj, "Mouth", "mouth", mask)
        out = self.split()
        z = object_z(out["Smile_mouth_L"]) + object_z(out["Smile_mouth_R"])
        np.testing.assert_allclose(z, 0.5, atol=1e-6)

    def test_renamed_reference_key(self):
        self.obj.data.shape_keys.reference_key.name = "Neutral"
        out = self.split()
        self.assertIn("Smile_L", out)
        self.assertNotIn("Neutral_L", out)

    def test_relative_key_is_respected(self):
        # "Wide" = Smile + 0.5 in Z, relative to Smile → effective delta is 0.5
        wide = self.obj.shape_key_add(name="Wide", from_mix=False)
        smile = self.obj.data.shape_keys.key_blocks["Smile"]
        co = key_co(smile)
        co[:, 2] += 0.5
        wide.data.foreach_set("co", co.reshape(-1))
        wide.relative_key = smile
        out = self.split()
        z = object_z(out["Wide_L"]) + object_z(out["Wide_R"])
        np.testing.assert_allclose(z, 0.5, atol=1e-6)

    def test_split_twice_replaces_outputs(self):
        first = sorted(self.split())
        second = sorted(self.split())
        self.assertEqual(first, second)
        self.assertFalse(any(".0" in n for n in second))

    def test_name_clash_outside_collection(self):
        clash = bpy.data.objects.new("Smile_L", None)
        bpy.context.scene.collection.objects.link(clash)
        self.split()
        preview = bpy.data.objects["Face_Preview"]
        self.assertIn("Smile_L", preview.data.shape_keys.key_blocks)
        self.assertIs(bpy.data.objects["Smile_L"], clash)

    def test_preview_mesh_matches_outputs(self):
        out = self.split()
        kbs = out["Face_Preview"].data.shape_keys.key_blocks
        for name in ("Smile_L", "Smile_R"):
            np.testing.assert_allclose(key_co(kbs[name])[:, 2], object_z(out[name]))

    def test_output_meshes_have_no_shape_keys(self):
        for name, o in self.split().items():
            if name != "Face_Preview":
                self.assertIsNone(o.data.shape_keys, name)

    def test_regenerate_refuses_to_clear_source_collection(self):
        col = bpy.data.collections.new("Src")
        bpy.context.scene.collection.children.link(col)
        col.objects.link(self.obj)
        self.obj.shapekey_splitter.output_collection = "Src"
        with self.assertRaises(RuntimeError):
            run_op(bpy.ops.shapekey_splitter.regenerate_all, self.obj)
        self.assertIn("Face", bpy.data.objects)

    def test_edit_mode_changes_are_used(self):
        with bpy.context.temp_override(object=self.obj, active_object=self.obj):
            bpy.ops.object.mode_set(mode='EDIT')
        import bmesh
        bm = bmesh.from_edit_mesh(self.obj.data)
        layer = bm.verts.layers.shape["Smile"]
        for v in bm.verts:
            v[layer].z = 2.0
        bmesh.update_edit_mesh(self.obj.data)
        out = self.split()
        with bpy.context.temp_override(object=self.obj, active_object=self.obj):
            bpy.ops.object.mode_set(mode='OBJECT')
        z = object_z(out["Smile_L"]) + object_z(out["Smile_R"])
        np.testing.assert_allclose(z, 2.0, atol=1e-6)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

class TestPreview(unittest.TestCase):
    def setUp(self):
        reset_scene()
        self.obj = make_grid()
        cl = self.obj.shapekey_splitter.centerline
        cl.transition_type = 'LINEAR'
        cl.preview_shapekey = "Smile"
        self.smile_before = key_co(self.obj.data.shape_keys.key_blocks["Smile"]).copy()

    def preview_z(self):
        return key_co(self.obj.data.shape_keys.key_blocks[splitter.PREVIEW_KEY_NAME])[:, 2]

    def test_preview_never_touches_source_key(self):
        cl = self.obj.shapekey_splitter.centerline
        self.assertEqual(run_op(bpy.ops.shapekey_splitter.preview_start, self.obj), {'FINISHED'})
        self.assertTrue(is_preview_active(self.obj))
        x = vertex_x(self.obj)
        np.testing.assert_allclose(self.preview_z()[x < -0.05], 1.0)

        cl.preview_strength = 0.5
        cl.preview_side = 'R'
        np.testing.assert_allclose(self.preview_z()[x > 0.05], 0.5)
        np.testing.assert_array_equal(
            key_co(self.obj.data.shape_keys.key_blocks["Smile"]), self.smile_before
        )

        self.assertEqual(run_op(bpy.ops.shapekey_splitter.preview_stop, self.obj), {'FINISHED'})
        self.assertFalse(is_preview_active(self.obj))
        self.assertFalse(self.obj.show_only_shape_key)

    def test_saving_during_preview_keeps_source_key(self):
        run_op(bpy.ops.shapekey_splitter.preview_start, self.obj)
        path = os.path.join(tempfile.mkdtemp(), "preview.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        obj = bpy.data.objects["Face"]
        np.testing.assert_array_equal(key_co(obj.data.shape_keys.key_blocks["Smile"]), self.smile_before)
        self.assertTrue(is_preview_active(obj))          # still recoverable after reload
        self.assertEqual(run_op(bpy.ops.shapekey_splitter.preview_stop, obj), {'FINISHED'})
        self.assertFalse(is_preview_active(obj))

    def test_preview_key_is_not_split(self):
        self.obj.shapekey_splitter.include_full_lr = True
        run_op(bpy.ops.shapekey_splitter.preview_start, self.obj)
        run_op(bpy.ops.shapekey_splitter.split_all, self.obj)
        names = outputs(self.obj)
        self.assertFalse(any(splitter.PREVIEW_KEY_NAME in n for n in names))

    def test_preview_uses_disabled_mask(self):
        x = vertex_x(self.obj)
        m = add_mask(self.obj, "Mouth", "mouth", {int(i): 1.0 for i in np.where(x < -0.1)[0]})
        m.enabled = False
        cl = self.obj.shapekey_splitter.centerline
        cl.preview_mask = "Mouth"
        run_op(bpy.ops.shapekey_splitter.preview_start, self.obj)
        z = self.preview_z()
        np.testing.assert_allclose(z[x < -0.1], 1.0)
        np.testing.assert_allclose(z[x >= -0.1], 0.0)

    def test_object_rename_during_preview(self):
        run_op(bpy.ops.shapekey_splitter.preview_start, self.obj)
        self.obj.name = "Renamed"
        self.assertEqual(run_op(bpy.ops.shapekey_splitter.preview_stop, self.obj), {'FINISHED'})
        np.testing.assert_array_equal(
            key_co(self.obj.data.shape_keys.key_blocks["Smile"]), self.smile_before
        )


# ---------------------------------------------------------------------------
# Masks and mirroring
# ---------------------------------------------------------------------------

class TestMasks(unittest.TestCase):
    def setUp(self):
        reset_scene()
        self.obj = make_grid()

    def test_mirror_matches_brute_force_and_prunes_zeros(self):
        x = vertex_x(self.obj)
        n = len(x)
        rng = np.random.default_rng(1)
        left = {int(i): float(rng.random()) for i in np.where(x < -0.001)[0] if rng.random() > 0.5}
        # stale right-side weights that must be removed where the mirror is unweighted
        stale = {int(i): 1.0 for i in np.where(x > 0.001)[0]}
        add_mask(self.obj, "Mouth", "mouth", {**left, **stale})
        run_op(bpy.ops.shapekey_splitter.mirror_weights, self.obj, vertex_group="mouth")

        co = np.empty(n * 3, np.float32)
        self.obj.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        w = get_vertex_group_weights(self.obj, "mouth")
        for li in np.where(x < -0.001)[0]:
            mirror = co[li] * [-1, 1, 1]
            ri = int(np.argmin(np.sum((co - mirror) ** 2, axis=1)))
            self.assertAlmostEqual(float(w[ri]), left.get(int(li), 0.0), places=5)
        vg = self.obj.vertex_groups["mouth"]
        members = sum(1 for v in self.obj.data.vertices for g in v.groups if g.group == vg.index)
        self.assertEqual(members, 2 * len(left))

    def test_global_mirror_skips_single_side_masks(self):
        x = vertex_x(self.obj)
        eye = {int(i): 1.0 for i in np.where(x < -0.1)[0]}
        add_mask(self.obj, "Eye_L", "eye_l", eye, bilateral=False)
        add_mask(self.obj, "Mouth", "mouth", {int(np.argmin(x)): 1.0})
        run_op(bpy.ops.shapekey_splitter.mirror_weights, self.obj)
        w = get_vertex_group_weights(self.obj, "eye_l")
        self.assertEqual(float(w[x > 0].sum()), 0.0)
        self.assertEqual(float(get_vertex_group_weights(self.obj, "mouth")[int(np.argmax(x))]), 1.0)

    def test_rename_does_not_hijack_existing_group(self):
        add_mask(self.obj, "Mouth", "mouth", {0: 1.0})
        self.obj.vertex_groups.new(name="lips")
        with self.assertRaises(RuntimeError):
            run_op(bpy.ops.shapekey_splitter.mask_rename, self.obj, new_name="Lips")
        m = self.obj.shapekey_splitter.masks[0]
        self.assertEqual((m.name, m.vertex_group), ("Mouth", "mouth"))

    def test_rename_updates_group_and_preview_mask(self):
        add_mask(self.obj, "Mouth", "mouth", {0: 1.0})
        self.obj.shapekey_splitter.centerline.preview_mask = "Mouth"
        run_op(bpy.ops.shapekey_splitter.mask_rename, self.obj, new_name="Upper Lip")
        m = self.obj.shapekey_splitter.masks[0]
        self.assertEqual((m.name, m.vertex_group), ("Upper Lip", "upper_lip"))
        self.assertIn("upper_lip", self.obj.vertex_groups)
        self.assertEqual(self.obj.shapekey_splitter.centerline.preview_mask, "Upper Lip")


# ---------------------------------------------------------------------------
# Shape key selection
# ---------------------------------------------------------------------------

class TestKeySelection(unittest.TestCase):
    def setUp(self):
        reset_scene()
        self.obj = make_grid()
        self.obj.shape_key_add(name="Frown", from_mix=False)
        self.obj.shapekey_splitter.include_full_lr = True

    def split_names(self):
        self.assertEqual(run_op(bpy.ops.shapekey_splitter.regenerate_all, self.obj), {'FINISHED'})
        preview = outputs(self.obj)["Face_Preview"]
        return sorted(k.name for k in preview.data.shape_keys.key_blocks[1:])

    def test_all_keys_selected_by_default(self):
        self.assertEqual(self.split_names(), ["Frown_L", "Frown_R", "Smile_L", "Smile_R"])

    def test_unchecked_key_is_not_split(self):
        run_op(bpy.ops.shapekey_splitter.key_toggle, self.obj, name="Frown")
        self.assertEqual(self.split_names(), ["Smile_L", "Smile_R"])
        self.assertNotIn("Frown_L", outputs(self.obj))
        run_op(bpy.ops.shapekey_splitter.key_toggle, self.obj, name="Frown")
        self.assertEqual(self.split_names(), ["Frown_L", "Frown_R", "Smile_L", "Smile_R"])

    def test_clear_selection_and_select_all(self):
        run_op(bpy.ops.shapekey_splitter.keys_clear_selection, self.obj)
        with bpy.context.temp_override(object=self.obj, active_object=self.obj):
            self.assertFalse(bpy.ops.shapekey_splitter.split_all.poll())
            self.assertFalse(bpy.ops.shapekey_splitter.regenerate_all.poll())
        run_op(bpy.ops.shapekey_splitter.keys_select_all, self.obj)
        self.assertEqual(self.split_names(), ["Frown_L", "Frown_R", "Smile_L", "Smile_R"])

    def test_new_keys_are_selected(self):
        run_op(bpy.ops.shapekey_splitter.keys_clear_selection, self.obj)
        self.obj.shape_key_add(name="Blink", from_mix=False)
        self.assertEqual(self.split_names(), ["Blink_L", "Blink_R"])

    def test_selection_is_saved(self):
        run_op(bpy.ops.shapekey_splitter.key_toggle, self.obj, name="Smile")
        path = os.path.join(tempfile.mkdtemp(), "selection.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        self.obj = bpy.data.objects["Face"]
        self.assertEqual(self.split_names(), ["Frown_L", "Frown_R"])


# ---------------------------------------------------------------------------
# Test scene (skipped if the .blend is missing)
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.path.exists(TEST_SCENE), "test scene not present")
class TestScene(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.open_mainfile(filepath=TEST_SCENE)
        self.obj = bpy.data.objects["Ghetto_Asian"]
        bpy.context.view_layer.objects.active = self.obj

    def test_regenerate_and_mirror(self):
        t = time.time()
        self.assertEqual(run_op(bpy.ops.shapekey_splitter.regenerate_all, self.obj), {'FINISHED'})
        self.assertEqual(run_op(bpy.ops.shapekey_splitter.mirror_weights, self.obj), {'FINISHED'})
        print(f"\n  test scene regenerate + mirror: {time.time() - t:.2f}s", end=" ")
        names = set(outputs(self.obj))
        self.assertIn("Ghetto_Asian_Smile_mouth_L", names)
        self.assertIn("Ghetto_Asian_Preview", names)


if __name__ == "__main__":
    shapekey_splitter.register()
    try:
        result = unittest.main(argv=[sys.argv[0], "-v"], exit=False).result
    finally:
        shapekey_splitter.unregister()
    sys.exit(0 if result.wasSuccessful() else 1)
