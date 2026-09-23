# Known issues / debugging backlog

Found while reviewing the imported code (v1.0.0). None of these are fixed yet.

## Correctness

1. **Center line is only centered when `blend_falloff == 2 * blend_distance`.**
   `compute_centerline_weights` ramps from `x = -blend_distance` to
   `x = -blend_distance + blend_falloff`, but only forces the left weight to 0 past
   `x = blend_distance + blend_falloff`. The 50/50 point is therefore at
   `x = blend_falloff/2 - blend_distance`: at the defaults (0.05 / 0.1) that is X=0,
   but any other combination shifts the seam off center.
2. **Single-side masks only work on the left.** Non-bilateral masks are always multiplied
   by `weight_L`, so a right-side mask (e.g. `Eye_R`) produces an all-zero output.
3. **`center_threshold` is not used by the split.** The plan caps center-vertex mask weight
   at 0.5. Right now the value only drives weight mirroring and the (unused) preview update.
4. **The delta is always taken against a key called `"Basis"`.** A renamed reference key
   makes the split silently output nothing, and each key's `relative_key` is ignored.
5. **Running Split All twice without Regenerate leaves duplicates.** Name clashes with objects
   already in the collection get Blender's `.001` suffixes, and those suffixes end up as the
   preview mesh's shape key names.
6. **Mesh data is stale in Edit Mode.** Split / mirror do not leave Edit Mode first, so edits
   that are not yet synced are ignored.

## Preview mode

7. **Preview writes into the real shape key.** If the file is saved while preview is on, the
   modified shape key is saved too. `preview_active` is `SKIP_SAVE`, so after reopening the
   file there is nothing left to restore.
8. The backup is a module-level dict keyed by `(obj.name, sk_name)`. It goes stale on undo,
   on an object rename, or on an add-on reload.
9. Disabled masks chosen in the preview mask field fall back silently to the plain L split.

## Masks / UI

10. Default masks are `Eyes` / `Mouth` (bilateral). The plan and the operator description
    say `Mouth`, `Eye_L`, `Eye_R` with `sks_` vertex group names.
11. The mask name can drift from the vertex group name (vertex groups are case-sensitive).
    The split uses `mask.name.lower()` for output names, not the vertex group.
12. `keep_original` is defined but never used or shown.

## Performance

13. `build_symmetry_map` runs a Python loop over every left vertex against all right vertices
    (O(N²)). Use a `mathutils.kdtree.KDTree`.
14. `get_vertex_group_weights` iterates every vertex in Python once per mask per shape key.
    Cache the weights per mask for the whole batch.

## Packaging

15. `blender_manifest.toml` still has the placeholder `maintainer = "Developer"` and copyright.
