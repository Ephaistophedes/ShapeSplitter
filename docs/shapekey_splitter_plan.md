# Blender 5 — Shape Key Splitter Add-on: Full Coding Plan

---

## 1. Project Overview

A Blender 5 add-on that splits shape keys into directional and region-masked variants using painted vertex weights. The user paints weights on the **left side only**; the add-on mirrors them automatically. All settings persist in the `.blend` file. Output targets game engines (Unity/Unreal).

---

## 2. File & Module Structure

```
shapekey_splitter/
├── __init__.py               # Blender registration, bl_info
├── operators/
│   ├── __init__.py
│   ├── op_split.py           # Batch split operator (all shape keys at once)
│   ├── op_mirror_weights.py  # Mirror left→right weight operator
│   ├── op_preview.py         # Enter/exit interactive preview mode
│   └── op_masks.py           # Add / remove / rename mask regions
├── ui/
│   ├── __init__.py
│   ├── panel_main.py         # N-panel sidebar root panel
│   ├── panel_centerline.py   # Center line sub-panel (blend sliders + preview)
│   └── panel_masks.py        # Mask regions list + controls
├── core/
│   ├── __init__.py
│   ├── weights.py            # Weight sampling, transition curves, mirroring logic
│   ├── splitter.py           # Shape key delta splitting algorithm
│   └── centerline.py         # Center line vertex classification + blending
├── data/
│   ├── __init__.py
│   └── props.py              # All PropertyGroups (stored in blend file)
└── utils/
    ├── __init__.py
    └── mesh_utils.py         # Vertex lookup helpers, symmetry snap, naming
```

---

## 3. Blender 5 Registration (`__init__.py`)

```python
bl_info = {
    "name": "Shape Key Splitter",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Shape Splitter",
    "description": "Split shape keys by axis and painted mask regions",
    "category": "Mesh",
}
```

- Use `bpy.utils.register_class` / `unregister_class` for every operator, panel, and property group.
- Attach the root `ShapeKeySplitterSettings` PropertyGroup to `bpy.types.Object` so data is per-object and saves with the blend file.
- Register all default masks on first use via a one-time initialisation check in `panel_main.py`'s `draw()`.

---

## 4. Data / Property Groups (`data/props.py`)

### 4.1 `MaskRegionItem` (per mask in the list)
```
name          : StringProperty   — display name (e.g. "Mouth", "Eye_L")
vertex_group  : StringProperty   — name of the vertex group on the mesh
enabled       : BoolProperty     — toggle this mask on/off without deleting it
is_bilateral  : BoolProperty     — True = generates _L and _R outputs, False = single output
is_default    : BoolProperty     — marks built-in defaults (Mouth, Eye_L, Eye_R)
```

### 4.2 `CenterLineSettings`
```
blend_distance    : FloatProperty  — world-space distance from X=0 where blending starts (default 0.05)
blend_falloff     : FloatProperty  — world-space distance over which the blend transitions (default 0.1)
transition_type   : EnumProperty   — LINEAR | SMOOTH | BELL | EASE_IN | EASE_OUT | EASE_IN_OUT
center_threshold  : FloatProperty  — verts within this distance of X=0 are "center verts" (default 0.001)
preview_active    : BoolProperty   — is live preview mode on?
preview_shapekey  : StringProperty — which shape key is being previewed
preview_strength  : FloatProperty  — 0.0–1.0 scrub slider shown during preview
```

### 4.3 `ShapeKeySplitterSettings` (root, attached to `Object`)
```
masks             : CollectionProperty(type=MaskRegionItem)
active_mask_index : IntProperty
centerline        : PointerProperty(type=CenterLineSettings)
naming_separator  : StringProperty  — default "_"  (so smile → smile_L / smile_R)
keep_original     : BoolProperty    — always True per spec, but exposed for future use
```

---

## 5. Core Algorithms (`core/`)

### 5.1 Center Line Classification (`centerline.py`)

**Vertex classification:**
```
x < -threshold         → LEFT side
x > +threshold         → RIGHT side
|x| <= threshold       → CENTER (on the seam)
```

**Weight for LEFT shape key at position x:**
```
if x > blend_distance + blend_falloff:   weight = 0.0   (fully right side, no influence)
if x < -(blend_distance):                weight = 1.0   (fully left side, full influence)
otherwise:                               weight = transition_curve(t)
    where t = (x - (-blend_distance)) / blend_falloff  clamped [0,1]
    weight = 1.0 - curve(t)
```

**RIGHT shape key weight = 1.0 - LEFT weight** (the complementary rule you specified).

This guarantees: `left_weight + right_weight == 1.0` at every vertex, preventing deformation artefacts when both sides are active simultaneously.

**Center verts (|x| <= threshold):** receive `weight = 0.5` on both L and R so they move half as much in each split — they contribute equally to both without doubling up.

### 5.2 Transition Curves (`weights.py`)

Implement each as a function `f(t) -> float` where `t` is in `[0, 1]`:

| Name | Formula |
|------|---------|
| LINEAR | `t` |
| SMOOTH | `3t² - 2t³` (smoothstep) |
| BELL | `smoothstep` applied twice (tent curve peaked at 0.5) |
| EASE_IN | `t²` |
| EASE_OUT | `1 - (1-t)²` |
| EASE_IN_OUT | standard cubic ease |

### 5.3 Weight Mirroring (`core/weights.py` — `mirror_weights_left_to_right`)

1. Build a **symmetry map**: for every vertex on the left side (x < 0), find its mirror on the right side (x > 0) by searching for the closest vertex to `(-x, y, z)` within `center_threshold` tolerance.
2. For each mask vertex group: copy left-side weights to their right-side mirrors.
3. **UI note:** Display a persistent info label in the panel — *"Paint weights on the LEFT side only — right side is auto-generated."*
4. Expose as a standalone operator button so user can re-mirror at any time without doing a full split.

### 5.4 Shape Key Splitting (`core/splitter.py`)

**For each shape key `SK` (excluding Basis):**

For each vertex `v`:

1. Get the raw delta: `delta[v] = SK.data[v].co - basis.data[v].co`
2. Compute `cl_weight_L[v]` and `cl_weight_R[v]` from center line rules (section 5.1).
3. For each active mask `M`:
   - Get `mask_weight[v]` from vertex group `M.vertex_group` (0.0 if vertex not in group).
   - **Center line interaction rule:** if `|v.x| <= center_threshold`, cap `mask_weight[v]` to 0.5.
   - If `v.x > 0` (right side of mesh), **zero out** the mask weight — left-side painting only. The mirrored weight (from 5.3) already handles the right side correctly.
4. Compute final left and right weights:
   ```
   final_L[v] = cl_weight_L[v] * (1.0 + mask_weight[v] * mask_influence)
   final_R[v] = cl_weight_R[v] * (1.0 - mask_weight[v] * mask_influence)
   ```
   Clamp both to [0, 1].
5. Create `SK_L`: `SK_L.data[v].co = basis.data[v].co + delta[v] * final_L[v]`
6. Create `SK_R`: `SK_R.data[v].co = basis.data[v].co + delta[v] * final_R[v]`
7. Keep original `SK` (muted or unmuted — user's choice per `keep_original`).

**Naming:**
- `SK.name + separator + "L"` → e.g. `smile_L`
- `SK.name + separator + "R"` → e.g. `smile_R`
- Masked region splits: `SK.name + "_" + mask.name` → e.g. `smile_mouth`

---

## 6. Operators (`operators/`)

### 6.1 `SHAPEKEY_OT_split_all` (`op_split.py`)
- **Trigger:** "Split All Shape Keys" button.
- Iterates all shape keys on active object (skip Basis).
- For each split result, duplicates the mesh and bakes the delta into vertex positions (calls `splitter.split_to_mesh(obj, sk, settings)`).
- Links each duplicate into the output collection (`{object.name}_ShapeSplits`), creating the collection if needed.
- Reports count at end: *"Generated 24 meshes in 'Head_ShapeSplits'."*
- Poll: object must be MESH, must have shape keys, must have at least one mask defined.

### 6.1b `SHAPEKEY_OT_regenerate_all` (`op_split.py`)
- Clears all objects currently in the output collection.
- Re-runs the full split, identical to `split_all`.
- Exposed as "Regenerate All" button — intended for iterating after weight painting changes.

### 6.2 `SHAPEKEY_OT_mirror_weights` (`op_mirror_weights.py`)
- **Trigger:** "Mirror Weights L→R" button (per mask or global).
- Calls `weights.mirror_weights_left_to_right(obj, vertex_group_name)`.
- Can be run independently at any time.
- Poll: object must be in Object or Weight Paint mode.

### 6.3 `SHAPEKEY_OT_preview_start` / `SHAPEKEY_OT_preview_stop` (`op_preview.py`)
- **Start:** stores original shape key values → sets `preview_active = True` → applies a temporary split preview using `splitter` logic with a driver or direct vertex position override.
- **Stop:** restores original state → `preview_active = False`.
- **Live update:** the `preview_strength` FloatProperty uses an `update` callback that re-runs the preview split at the new strength value every time the slider moves.
- **Which shape key to preview:** dropdown populated from the mesh's shape key list.

### 6.4 `SHAPEKEY_OT_mask_add` / `SHAPEKEY_OT_mask_remove` / `SHAPEKEY_OT_mask_rename` (`op_masks.py`)
- Add: creates a new `MaskRegionItem` + creates the corresponding vertex group on the mesh if it doesn't exist.
- Remove: removes `MaskRegionItem` (does NOT delete the vertex group — non-destructive).
- Rename: renames both the item and the vertex group simultaneously.

### 6.5 `SHAPEKEY_OT_init_defaults` (called from panel draw on first use)
- Checks if default masks exist; if not, creates: `Mouth`, `Eye_L`, `Eye_R` as `MaskRegionItem` entries and creates matching vertex groups.

---

## 7. UI Panels (`ui/`)

### 7.1 N-Panel Root (`panel_main.py`)
**Tab name:** "Shape Splitter"  
**Space:** VIEW_3D, region N-PANEL

Layout:
```
[ Shape Key Splitter ]
─────────────────────
⚠ Paint weights on the LEFT SIDE only.
  Right side is auto-generated.
─────────────────────
Naming Separator:  [ _ ]
[  Split All Shape Keys  ]   ← main action button, prominent
─────────────────────
▶ Center Line Settings       ← collapsible sub-panel
▶ Mask Regions               ← collapsible sub-panel
```

### 7.2 Center Line Sub-Panel (`panel_centerline.py`)

```
CENTER LINE SETTINGS
────────────────────
Transition Type:   [ SMOOTH ▼ ]
Blend Start:       [====|   ] 0.050
Blend Falloff:     [===|    ] 0.100
Center Threshold:  [=|      ] 0.001

─ Preview ─
Shape Key:         [ smile ▼ ]
[ ▶ Enter Preview Mode ]
  (if preview active:)
  Strength:        [========] 0.75
[ ■ Exit Preview  ]

[ Mirror Weights L→R (Global) ]
```

- All sliders call `update` callbacks that recalculate the preview in real time when `preview_active` is True.
- Visual indicator (icon change, highlighted border) when preview is active so user knows they're in a temporary state.

### 7.3 Mask Regions Sub-Panel (`panel_masks.py`)

```
MASK REGIONS
────────────
┌─────────────────────────────────────┐
│ ☑ Mouth    [sks_mouth]   [L+R ✅]  │
│ ☑ Eye_L    [sks_eye_L]   [L+R ❌]  │
│ ☑ Eye_R    [sks_eye_R]   [L+R ❌]  │
│ ☑ My Mask  [my_vg     ]   [L+R ✅]  │
└─────────────────────────────────────┘
[ + Add Mask ]  [ - Remove ]  [ Rename ]

Selected Mask: "Mouth"
  Vertex Group: [ sks_mouth ▼ ]  ← dropdown of existing vertex groups
  Bilateral (L+R):  [✅]          ← toggle; affects output naming
  [ Mirror Weights L→R ]          ← per-mask mirror button
  [ Select Vertices ]             ← enters Weight Paint with this group active
```

- The list uses `bpy.types.UIList` for clean scrollable display.
- Enabled checkbox per row toggles the mask without removing it.
- "Select Vertices" button: sets object to Weight Paint mode and activates the relevant vertex group for immediate painting.

---

## 8. Center Line + Custom Mask Interaction Rules

This is critical for correctness. The rules, implemented in `splitter.py`:

1. **Left-side painting only.** Any painted weight on `x > 0` (right side) is **ignored** — only mirrored weights count on the right.
2. **Center verts** (`|x| <= center_threshold`): mask weight is hard-capped at `0.5` regardless of painted value. This prevents center verts from being pulled fully into one side by a mask.
3. **Mask amplifies the center-line split**, it does not replace it. The center line weight is always the base; the mask adds directional bias on top.
4. If a user paints over the center line with a mask (e.g. mouth mask covering lip center verts), rule 2 ensures those verts respect the complementary rule and never cause artefacts.
5. Final weights are always clamped to `[0, 1]` and `L + R` always sums to `≤ 1.0` per vertex to prevent over-extension.

---

## 9. Default Mask Regions

Pre-loaded on first add-on use (stored per-object in blend file):

| Display Name | Vertex Group Name | Bilateral |
|---|---|---|
| Mouth | `sks_mouth` | ✅ Yes → produces `_mouth_L`, `_mouth_R` |
| Eye_L | `sks_eye_L` | ❌ No → produces `_eye_L` only |
| Eye_R | `sks_eye_R` | ❌ No → produces `_eye_R` only |

Naming prefix `sks_` avoids conflicts with user's own vertex groups.

---

## 10. Naming Convention

Every mask that covers **both sides of the face** produces its own L/R pair. Single-side masks produce one output only.

| Operation | Input | Output |
|---|---|---|
| L/R axis split | `smile` | `smile_L`, `smile_R` |
| Bilateral mask (e.g. Mouth) | `smile` + mask `Mouth` | `smile_mouth_L`, `smile_mouth_R` |
| Single-side mask (e.g. Eye_L) | `smile` + mask `Eye_L` | `smile_eye_L` |
| Single-side mask (e.g. Eye_R) | `smile` + mask `Eye_R` | `smile_eye_R` |
| Custom separator | `smile` (sep=`.`) | `smile.L`, `smile.R` |

**Bilateral vs single-side mask:** each `MaskRegionItem` has a `is_bilateral: BoolProperty` field. Default masks: `Mouth` = bilateral, `Eye_L` = single-side, `Eye_R` = single-side. User-created masks default to bilateral and can be toggled in the mask list UI.

Separator is configurable in the root panel (default `_`).

---

## 11. Blend File Persistence

- All data stored in `obj.shapekey_splitter` (a PointerProperty on `bpy.types.Object`).
- This means masks, center line settings, and separator preferences save and reload automatically with the `.blend` file.
- No external files, no JSON, no scene-level properties — purely object-level so multi-object scenes work independently per object.

---

## 12. Output — Duplicated Meshes in a Collection

Instead of modifying shape keys on the original mesh, each split result is output as a **separate duplicated mesh object** placed in a dedicated Blender collection.

### 12.1 Output Collection Structure

```
Scene Collection
└── [ObjectName]_ShapeSplits/        ← auto-created collection, named after source object
    ├── [ObjectName]_Preview          ← duplicate base mesh with ALL split shape keys added
    ├── smile_L                       ← mesh object, shape frozen into geometry
    ├── smile_R
    ├── smile_mouth
    ├── brow_raise_L
    ├── brow_raise_R
    └── ...
```

- Collection name: `{object.name}_ShapeSplits`
- If the collection already exists, new objects are added to it (no duplicate collections created).
- Objects in the collection are hidden from render by default (`obj.hide_render = True`) — they are reference meshes, not renderable.

### 12.1b Preview Mesh — `[ObjectName]_Preview`

This is the most useful object in the collection for the artist. It is a full duplicate of the source mesh that lets the user test all split shapes interactively without touching the original.

**How it is built:**

1. Duplicate the source object (`obj.copy()` + `obj.data.copy()`), name it `{object.name}_Preview`.
2. **Clear all existing shape keys** from the duplicate — start from a clean Basis (the neutral rest pose geometry, no expressions).
3. For every generated split result (e.g. `smile_L`, `smile_R`, `smile_mouth`):
   - Add a new shape key to the preview mesh with the matching name.
   - Copy the baked vertex positions from the corresponding split mesh object into that shape key's `data[i].co`.
4. The preview mesh now has a full shape key stack of all generated splits, all at value `0.0` by default.
5. Link into the output collection alongside the individual split meshes.

**Result:** The artist can open the Shape Keys panel on `[ObjectName]_Preview`, scrub `smile_L` to `1.0`, `smile_R` to `1.0`, verify they blend cleanly with no artefacts, and test any combination — all without modifying the source object.

**Important:** The preview mesh is always regenerated from scratch on "Regenerate All". It is never meant to be edited directly.

### 12.2 Per-Object Split Mesh Output

For each split result (e.g. `smile_L`):

1. **Duplicate** the source mesh object (`obj.copy()` + `obj.data.copy()`).
2. **Apply** the split delta directly into the vertex positions of the duplicate — the output mesh is a plain mesh with the expression "baked in", no shape keys.
3. **Name** the duplicate object and its mesh data after the split: `smile_L`.
4. **Link** the duplicate into the output collection only (unlink from any other collection).
5. The duplicate inherits the source object's transforms, materials, and UV maps.

### 12.3 Preview Mesh Build Order

The preview mesh (`[ObjectName]_Preview`) must be built **after** all split meshes are generated, since it reads vertex positions back from them:

1. Generate all split meshes first (§12.2).
2. Duplicate source object → clear all shape keys → Basis only remains.
3. For each split mesh in the collection (in consistent order): add a shape key, copy positions from the split mesh's vertices.
4. All shape keys start at value `0.0`.

### 12.4 UI Controls

Add to the root panel:

```
Output Collection: [ Head_ShapeSplits ]  ← auto-filled, editable
[ Split All Shape Keys ]
[ Regenerate All ]                        ← clears collection and re-runs split
```

- "Regenerate All" clears all objects in the output collection (both split meshes and the preview mesh) before re-splitting.
- The preview mesh is always the first object listed in the collection for easy access in the outliner.

### 12.5 Source Object is Never Modified

- The original mesh and all its shape keys remain completely untouched.
- The output collection is purely additive — safe to delete and regenerate at any time.

---

## 13. Development Phases & Task Order

### Phase 1 — Foundation
- [ ] `__init__.py` with bl_info and registration scaffold
- [ ] `data/props.py` — all PropertyGroups defined and registered on `bpy.types.Object`
- [ ] Basic N-panel drawing (no operators yet, just layout)

### Phase 2 — Core Algorithms
- [ ] `core/centerline.py` — vertex classification + weight computation
- [ ] `core/weights.py` — all 6 transition curves + symmetry map builder + mirror function
- [ ] Unit-test weight curves with simple Python assertions (no Blender needed)

### Phase 3 — Splitting & Collection Output
- [ ] `core/splitter.py` — full split algorithm, outputs baked vertex positions (not shape keys)
- [ ] `operators/op_split.py` — batch split + regenerate operators, collection creation/clearing logic
- [ ] Test on a simple symmetric mesh with 1 shape key — verify collection is created and meshes are correct

### Phase 4 — Masks
- [ ] `operators/op_masks.py` — add/remove/rename mask operators
- [ ] `ui/panel_masks.py` — UIList + controls
- [ ] Default mask initialisation operator
- [ ] Per-mask mirror weights operator

### Phase 5 — Preview
- [ ] `operators/op_preview.py` — enter/exit preview with live strength slider
- [ ] `ui/panel_centerline.py` — sliders with update callbacks feeding live preview

### Phase 6 — Polish
- [ ] Warning labels in UI ("Paint LEFT side only")
- [ ] Poll messages on operators (clear error if mesh has no shape keys etc.)
- [ ] Naming separator UI
- [ ] FBX export tip label
- [ ] README / tooltip strings on every property

---

## 14. Key Blender 5 API Notes for Claude Code

- Use `bpy.props` for all properties — no plain Python attributes on ID types.
- `mesh.vertices[i].co` is in **local space** — if object has non-identity transforms, use `obj.matrix_world @ v.co` for world-space X comparisons, OR require the user to apply scale before using the add-on (document this clearly).
- Shape key deltas: `sk.data[i].co` gives the key's vertex position (not a delta). Delta = `sk.data[i].co - basis.data[i].co`.
- Vertex group weights: use `obj.vertex_groups[name].weight(vertex_index)` — wrap in try/except as it raises `RuntimeError` if the vertex is not in the group.
- For live preview: modify shape key `data[i].co` directly and call `mesh.update()` + `bpy.context.view_layer.update()` — do NOT use drivers (too slow for per-frame interactive scrubbing).
- **Mesh duplication:** `new_obj = obj.copy(); new_obj.data = obj.data.copy()` — then apply the split delta directly to `new_obj.data.vertices[i].co`. Do NOT carry over shape keys to the duplicate.
- **Collection management:** `bpy.data.collections.new(name)` to create; `bpy.context.scene.collection.children.link(col)` to add to scene; `col.objects.link(new_obj)` to place object; `bpy.context.scene.collection.objects.unlink(new_obj)` to remove from root collection if auto-linked.
- **Clearing a collection:** iterate `col.objects` and call `bpy.data.objects.remove(o, do_unlink=True)` — never just unlink, or mesh data will leak.
- `UIList` requires a `draw_item` method — use `layout.template_list(...)` in the panel.
- Blender 5: confirm whether `bpy.app.version >= (5, 0, 0)` deprecates any 4.x APIs used (particularly check `bmesh` attribute access and `ShapeKey.data` indexing).

---

## 15. Known Edge Cases to Handle

| Case | Handling |
|---|---|
| Asymmetric mesh (no mirror counterpart) | Skip mirroring for unmatched verts, log a warning |
| Shape key already named `smile_L` | Append number suffix: `smile_L_001` |
| Vertex not in any mask group | Treat mask weight as 0.0 (pure center line split) |
| Object has no shape keys | Operator polls False, button greyed out with tooltip |
| Object scale not applied | Show warning in panel if `obj.scale != (1,1,1)` |
| Multiple objects selected | Operate only on the **active** object |
| Center vert with mask weight > 0.5 | Hard-cap to 0.5 (documented in tooltip) |
