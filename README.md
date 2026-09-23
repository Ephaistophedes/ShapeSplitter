# Shape Key Splitter

A Blender 5 add-on that splits shape keys into **left / right** and **region-masked** variants,
using a configurable center-line blend and painted vertex-group masks. It is built for making
game-engine blendshapes (Unity / Unreal). Every split is baked into its own mesh object in an
output collection, and a preview mesh gathers all the splits back together as shape keys.

> **Status:** v1.3.0. The first debugging pass is done (see [CHANGELOG.md](CHANGELOG.md));
> open items are tracked in [docs/known_issues.md](docs/known_issues.md).

## Features

- **Center-line L/R split** with a transition zone centered on X = 0. You set its width and
  curve (Linear, Smooth, Bell, Ease In, Ease Out, Ease In/Out). `L + R = 1` at every vertex,
  so the two halves always add up to the original shape, and `R` is an exact mirror image
  of `L`. Seam vertices (within *Center Threshold* of X = 0) are split exactly 50/50.
- **Mask regions** backed by vertex groups:
  - *Bilateral* masks give `<key>_<mask>_L` and `<key>_<mask>_R`.
  - *Single-side* masks give `<key>_<mask>`. The painted weights alone define the region,
    so they work on either side, e.g. `Eye_L` and `Eye_R`.
- **Shape key selection**: a checklist of the mesh's shape keys, with *Select All* and
  *Clear Selection*, so only the keys you need are split and exported.
- **Mirror weights L→R**: paint the left side, then copy the weights to the matching
  right-side vertices. Works per mask or for all enabled bilateral masks. Single-side masks
  are never mirrored.
- **Live preview** of the split on one shape key, with controls for strength, mask and side.
  The result is shown on a temporary `SKS_Preview` shape key, and your shape keys are
  never modified.
- **Non-destructive output**: the source object is never changed. Results go into
  `<Object>_ShapeSplits`:
  - one mesh per split, with the shape baked into the geometry
  - `<Object>_Preview`, which carries every split as a shape key for testing combinations
- All settings are saved per object in the `.blend` file.

## Requirements

- Blender **5.0** or newer (the add-on is packaged as an extension with `blender_manifest.toml`).

## Installation

Build the extension zip from the add-on folder:

```sh
blender --command extension build --source-dir shapekey_splitter --output-dir .
```

In Blender, go to **Edit → Preferences → Get Extensions**, open the **▾** menu and choose
**Install from Disk…**, then pick the zip.

For development, you can link `shapekey_splitter/` into a local extensions repository (for
example `~/.config/blender/5.0/extensions/user_default/shapekey_splitter`) and reload
scripts after each change.

## Usage

Open the **3D Viewport → Sidebar (N) → Shape Splitter** tab with a mesh selected.

1. **Apply scale** (Ctrl+A) on the mesh. The panel warns you if it is not applied. The
   mesh should be symmetric across local X = 0. Each shape key is split using its delta
   against its own *Relative To* key, as Blender evaluates it.
2. **Center Line Settings**: pick the transition curve and blend width.
3. **Mask Regions** (optional): add masks, or click *Add Default Masks*. Use *Edit Mask*
   to paint each vertex group in Weight Paint mode, then *Mirror Weights L→R* (or paint
   with X-Mirror on).
4. **Preview** (optional): pick a shape key and, if you want, a mask and side. Click
   *Enter Preview Mode* and adjust the settings live. Click *Exit Preview* to remove the
   temporary `SKS_Preview` key. If you save while previewing, the key is saved too, and
   the panel offers *Exit Preview* after you reopen the file.
5. In the **Shape Keys** list, check the keys you want to export (all are checked by
   default, including keys you add later). Use *Select All* / *Clear Selection* for bulk
   changes and the list's filter field to search by name.
6. Pick the **Output** collection from the dropdown, or leave it empty to use (and create)
   `<Object>_ShapeSplits`. Collections that contain the source object are not offered.
7. Click **Split All Shape Keys**. It splits the checked keys and replaces outputs of the same name in the
   output collection. Outputs of unchecked keys from earlier runs are left alone. **Regenerate All** clears the collection first, so it holds only the checked keys'
   outputs.

### Output naming (separator `_`)

| Source | Output |
| --- | --- |
| `smile`, *Include Full L/R* on | `smile_L`, `smile_R` |
| `smile` + bilateral mask `Mouth` | `smile_mouth_L`, `smile_mouth_R` |
| `smile` + single-side mask `Eye_L` | `smile_eye_l` |

You can change the separator in the main panel (for example `.` gives `smile.L`).

## Running the tests

The tests run the add-on headless inside Blender, on synthetic meshes and on
`test_scenes/Test_Scene.blend`:

```sh
blender -b --factory-startup --python tests/run_tests.py
# or, with the bpy module from PyPI (Python 3.11):
pip install bpy==5.0.0 && python tests/run_tests.py
```

## Repository layout

```
shapekey_splitter/        The add-on (extension root, contains blender_manifest.toml)
  core/                   Pure algorithms: center-line weights, curves, mirroring, splitting
  data/                   PropertyGroups (stored on bpy.types.Object.shapekey_splitter)
  operators/              Split, regenerate, mirror, preview and mask operators
  ui/                     Sidebar panels and the mask UIList
  utils/                  Mesh/vertex-group helpers
docs/
  shapekey_splitter_plan.md            Original design plan
  blender5_addon_development_guide.md  Blender 5 API / extension reference notes
  known_issues.md                      Open issues and limitations
tests/
  run_tests.py            Headless regression tests (unittest)
test_scenes/
  Test_Scene.blend        Scene for manual testing
```

## License

GPL-3.0-or-later (as declared in `shapekey_splitter/blender_manifest.toml`).
