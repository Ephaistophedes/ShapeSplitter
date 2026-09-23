# Changelog

## 1.1.0

Bug fixes from the first review of v1.0.0. Every fix has a test in `tests/run_tests.py`.

### Splitting
- **The center line is always centered on X = 0.** Before, the 50/50 point was at
  `falloff/2 - blend_start`, so it was only centered with the default values. The two
  settings are now one: **Blend Width**, the full width of a zone centered on X = 0. It
  keeps the old `blend_falloff` identifier, so the default 0.1 gives exactly the same
  result as before.
- **L and R are exact mirror images for every curve.** Ease In and Ease Out used to make R
  a different shape from L. They are now defined from the seam outwards: Ease In changes
  slowly at the seam, Ease Out changes fast at the seam.
- **Single-side masks work on the right side.** They used to be multiplied by the left
  weight, so a mask like `Eye_R` gave an empty output. The painted weights alone now
  define the region.
- **Center Threshold now affects the split.** Seam vertices are split exactly 50/50. Before,
  the value only affected mirroring.
- **The split no longer depends on a key named "Basis".** It uses the mesh's reference key
  and each key's *Relative To* key.
- **Running Split All again replaces outputs** instead of adding `.001` copies. If an object
  outside the collection already has the same name, you get a warning, and the preview mesh
  still uses the intended shape key name.
- **Edit Mode changes are included.** Split syncs Edit Mode changes to the mesh before it
  reads it.
- **Regenerate All will not clear a collection that contains the source object.**
- **The output collection is linked into the scene again** if it exists but was unlinked.

### Preview
- **Preview no longer writes into your shape key.** It uses a temporary `SKS_Preview` key
  shown with Shape Key Lock. Saving mid-preview can no longer overwrite a key.
- **Preview can no longer get out of sync.** Whether preview is on now depends on whether
  the key exists, not on a separate flag and a module-level backup. It stays correct after
  undo, object renames, add-on reloads and reopening the file.
- The **Strength** slider is now visible while preview is on. **Side** also works without a
  mask.
- The panel shows a warning when the preview mask is missing or disabled. A disabled mask
  is still previewed, instead of silently falling back to the plain L split.

### Masks
- **Global Mirror skips single-side masks.** Before, it copied an `Eye_L` mask onto the
  right eye.
- **Mirroring removes vertices from the group instead of adding them with weight 0.** The
  test scene's mouth group had 13,607 of 13,927 vertices as members.
- **Renaming a mask to the name of an existing vertex group is refused.** Before, the mask
  silently switched to the other group. A rename also updates the preview's mask selection.
- Adding or renaming a mask with an empty name is refused.
- Fixed the *Add Default Masks* description (it adds Eyes and Mouth).
- The mask panel warns when a mask's vertex group is missing, and it hides the mirror
  button for single-side masks.

### Performance
- Mirroring uses a `mathutils` KD-tree instead of a brute-force search.
- Mask weights are read once per batch instead of once per shape key and mask. Outputs are
  copied from a mesh with no shape keys, instead of copying the full shape key stack and
  then stripping it for every output. On the test scene, Regenerate All takes 0.10 s,
  down from 0.20 s.

### Other
- Removed the unused `keep_original` setting. The source object is never modified.
- Manifest: version 1.1.0, real maintainer and copyright.
