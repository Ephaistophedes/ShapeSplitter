# Shape Key Splitter

A Blender 5 add-on that splits shape keys into **left / right** and **region-masked** variants,
using a configurable center-line blend and painted vertex-group masks. It is built for making
game-engine blendshapes (Unity / Unreal). Every split is baked into its own mesh object in an
output collection, and a preview mesh gathers all the splits back together as shape keys.

> **Status:** early (v1.0.0). It works end to end, but a debugging and improvement pass is
> in progress. See [docs/known_issues.md](docs/known_issues.md).

## Features

- **Center-line L/R split** with an adjustable blend start, falloff width and curve
  (Linear, Smooth, Bell, Ease In, Ease Out, Ease In/Out). `L + R = 1` at every vertex,
  so the two halves always add up to the original shape.
- **Mask regions** backed by vertex groups:
  - *Bilateral* masks give `<key>_<mask>_L` and `<key>_<mask>_R`.
  - *Single-side* masks give `<key>_<mask>`.
- **Mirror weights L→R**: paint the left side, then copy the weights to the matching
  right-side vertices. Works per mask or for all enabled masks.
- **Live preview** of the split on one shape key, with sliders for strength, mask and side.
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
   mesh should be symmetric across local X = 0, with a reference key named `Basis`.
2. **Center Line Settings**: pick the transition curve, blend start and falloff.
3. **Mask Regions** (optional): add masks, or click *Add Default Masks*. Use *Edit Mask*
   to paint each vertex group in Weight Paint mode, then *Mirror Weights L→R* (or paint
   with X-Mirror on).
4. **Preview** (optional): pick a shape key and, if you want, a mask and side. Click
   *Enter Preview Mode* and adjust the settings live. Click *Exit Preview* before you save
   the file (see known issues).
5. Click **Split All Shape Keys**. Use **Regenerate All** after you change weights or
   settings: it clears the output collection and runs the split again.

### Output naming (separator `_`)

| Source | Output |
| --- | --- |
| `smile`, *Include Full L/R* on | `smile_L`, `smile_R` |
| `smile` + bilateral mask `Mouth` | `smile_mouth_L`, `smile_mouth_R` |
| `smile` + single-side mask `Eye_L` | `smile_eye_l` |

You can change the separator in the main panel (for example `.` gives `smile.L`).

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
  known_issues.md                      Debugging backlog
test_scenes/
  Test_Scene.blend        Scene for manual testing
```

## License

GPL-3.0-or-later (as declared in `shapekey_splitter/blender_manifest.toml`).
