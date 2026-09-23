# Definitive guide to Blender 5 add-on development

**Blender 5.0 (released November 2025) introduced several breaking Python API changes that every add-on developer must address**, most critically the separation of `bpy.props` storage from custom IDProperties and the removal of the legacy Action API. Meanwhile, the extension system introduced in Blender 4.2 — with `blender_manifest.toml` replacing the old `bl_info` dictionary — is now the standard distribution path. This guide covers the full landscape of best practices for building robust, performant add-ons targeting Blender 4.2 through 5.x, synthesized from official developer documentation, API release notes, and battle-tested community patterns.

---

## 1. Registration has moved from bl_info to manifest-driven extensions

Since Blender 4.2, the `bl_info` dictionary is **deprecated** in favor of a standalone `blender_manifest.toml` file. Legacy add-ons with `bl_info` still work but install through a separate "Install Legacy Add-on" button and are considered a compatibility path, not the recommended approach.

The manifest uses semantic versioning and TOML syntax:

```toml
schema_version = "1.0.0"
id = "my_addon"
version = "1.0.0"
name = "My Add-on"
tagline = "Short description, max 64 characters"
maintainer = "Developer <email@example.com>"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]
copyright = ["2025 Developer Name"]

[permissions]
# files = "Import/export support"
# network = "Check for updates"

[build]
paths_exclude_pattern = ["__pycache__/", ".git/", "*.zip"]
```

Key manifest rules: the `id` must be a valid Python identifier, `tagline` cannot exceed 64 characters or end with punctuation, and all required fields must be non-empty. Empty strings or empty lists cause validation failures.

Class registration itself remains stable since Blender 2.80. The `register()` and `unregister()` functions are required, and classes must follow naming conventions — `CATEGORY_OT_name` for operators, `CATEGORY_PT_name` for panels, `CATEGORY_MT_name` for menus, `CATEGORY_PG_name` for property groups:

```python
classes = (
    MY_PG_properties,   # PropertyGroups first
    MY_OT_operator,
    MY_PT_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.my_props = bpy.props.PointerProperty(type=MY_PG_properties)

def unregister():
    del bpy.types.Scene.my_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

**Registration order is critical**: PropertyGroups must be registered before any class that references them. Using a set instead of a tuple or list for class ordering is a common bug — sets have no guaranteed order in Python, causing intermittent `missing bl_rna attribute` errors. Always use tuples or lists.

For extensions (4.2+), **use `__package__` instead of `__name__`** for the add-on identifier. The module namespace now includes the repository name (`bl_ext.{repo}.{addon_id}`), so hardcoding module names will break. For `AddonPreferences`, set `bl_idname = __package__`.

---

## 2. PropertyGroups persist data correctly when registered on ID types

A `PropertyGroup` is the proper mechanism for storing structured persistent data on Blender objects. Properties defined with annotation syntax (`:` colon, mandatory since 2.80) are saved to the `.blend` file when attached to ID types like `Scene`, `Object`, or `Material`. The class definition, however, is not saved — the add-on must be enabled when the file loads to access the data.

```python
class MySettings(bpy.types.PropertyGroup):
    threshold: bpy.props.FloatProperty(name="Threshold", default=0.5, min=0.0, max=1.0)
    target: bpy.props.PointerProperty(type=bpy.types.Object, poll=lambda self, obj: obj.type == 'MESH')
    items: bpy.props.CollectionProperty(type=MyItemGroup)
    active_index: bpy.props.IntProperty(default=0)
```

**`PointerProperty`** stores a single PropertyGroup instance or a reference to a Blender ID type (Object, Material, etc.). References survive renames. Use the `poll` parameter to filter valid targets in the UI. **`CollectionProperty`** stores a dynamic list of PropertyGroup instances, manipulated with `.add()`, `.remove(index)`, and `.clear()`. One important limitation: CollectionProperty does **not** support `update` callbacks, unlike every other property type.

For **session-only data** that should not persist across saves, use `bpy.types.WindowManager` with the `SKIP_SAVE` option:

```python
bpy.types.WindowManager.temp_data = bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
```

A known pitfall with `AddonPreferences`: properties inside a nested `PointerProperty` (a PropertyGroup within AddonPreferences) may not trigger the auto-save flag, meaning changes can be lost when Blender exits. Store critical preferences as flat properties directly on the `AddonPreferences` class rather than nesting them inside a PropertyGroup.

**Blender 5.0 introduced a critical change**: properties defined via `bpy.props` are no longer stored in the same container as user-defined Custom Properties. Dict-like access (`obj['property_name']`) no longer works for `bpy.props`-defined properties — use direct attribute access (`obj.property_name`) instead. New `get_transform`/`set_transform` callbacks were introduced as faster replacements for traditional get/set patterns, and a new `READ_ONLY` option flag replaces the old getter-only pattern.

---

## 3. Operators require careful poll, invoke, and modal patterns

The operator lifecycle involves three key methods with distinct purposes. **`execute(self, context)`** runs the operator's core logic and returns `{'FINISHED'}` or `{'CANCELLED'}`. **`invoke(self, context, event)`** initializes the operator from user interaction — it receives mouse/keyboard event data and typically either calls `self.execute(context)` directly or opens a dialog. **`modal(self, context, event)`** handles continuous interaction, receiving every input event until the operator finishes.

**`poll()` must be lightweight** because it's called on every UI redraw to determine whether the operator button should be grayed out:

```python
@classmethod
def poll(cls, context):
    return (context.object is not None and
            context.object.type == 'MESH' and
            context.mode == 'OBJECT')
```

For **modal operators**, the invoke method must call `context.window_manager.modal_handler_add(self)` and return `{'RUNNING_MODAL'}`. Always store initial state for cancellation recovery, and always handle ESC/right-click to cancel:

```python
def modal(self, context, event):
    if event.type == 'MOUSEMOVE':
        self.value = event.mouse_x
        self.execute(context)
    elif event.type == 'LEFTMOUSE':
        return {'FINISHED'}
    elif event.type in {'RIGHTMOUSE', 'ESC'}:
        context.object.location.x = self.init_loc_x  # Restore state
        return {'CANCELLED'}
    return {'RUNNING_MODAL'}
```

**`bl_options` configuration matters**: set `bl_options = {'REGISTER', 'UNDO'}` for any operator that modifies Blender data. Omitting `'UNDO'` corrupts the undo stack and can cause crashes. Blender 4.2 added `'MODAL_PRIORITY'` for modals that need to handle events before other modal operators.

Error reporting uses `self.report({'ERROR'}, "message")`, but beware: an `{'ERROR'}` report raises a `RuntimeError` in calling code regardless of the operator's return value. For non-fatal issues, use `{'WARNING'}` instead. Reports from programmatically called operators (not user-invoked) may not appear in the status bar — this is a known limitation.

---

## 4. UI panels register into the N-panel sidebar with specific type constants

For 3D Viewport sidebar panels (the N-panel), set `bl_space_type = 'VIEW_3D'`, `bl_region_type = 'UI'`, and `bl_category` to the desired tab name. Use mix-in classes to share common settings across related panels:

```python
class View3DPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "My Tools"

class MY_PT_MainPanel(View3DPanel, bpy.types.Panel):
    bl_idname = "VIEW3D_PT_my_main"
    bl_label = "Main Panel"
    def draw(self, context):
        self.layout.operator("object.my_operator")
```

For Properties editor panels, set `bl_space_type = 'PROPERTIES'` with `bl_region_type = 'WINDOW'` and `bl_context` to the target tab (`"object"`, `"scene"`, `"material"`, etc.).

**The `draw()` method is called on every redraw** of the panel area. Never perform heavy computation, file I/O, or large data iteration inside `draw()`. Use `layout.prop()` to bind directly to RNA properties (most efficient), and use `poll()` to prevent the panel from drawing when it shouldn't be visible.

For `layout.operator()`, it returns an operator properties object that allows setting parameters inline:

```python
op = layout.operator("my_list.move_item", text="Move Up")
op.direction = 'UP'
```

**UIList implementation** requires a `draw_item` method that handles all three layout types (`DEFAULT`, `COMPACT`, `GRID`). The UIList class, the item PropertyGroup, a CollectionProperty, and an IntProperty for the active index all must work together:

```python
class MY_UL_Items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='OBJECT_DATA')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OBJECT_DATA')

# In panel draw():
layout.template_list("MY_UL_Items", "", scene, "my_collection", scene, "active_index")
```

---

## 5. Mesh data access depends on mode and operation type

Blender exposes mesh geometry through four aligned arrays: `vertices`, `edges`, `loops`, and `polygons`. Direct mesh access (`bpy.types.Mesh`) works only in **Object Mode** and is optimized for compact storage and bulk operations. BMesh works in both modes but through different entry points.

**When to use which**:

- **Direct mesh + foreach_get/set**: Bulk read/write of vertex positions, normals, selections, UVs on large meshes. The fastest path for data transfer.
- **BMesh**: Topology operations (split, dissolve, merge, inset), edit-mode work, and any operation requiring connectivity awareness. Use `bmesh.from_edit_mesh(me)` in Edit Mode (live access, update with `bmesh.update_edit_mesh(me)`) and `bmesh.new(); bm.from_mesh(me)` in Object Mode (independent copy, write back with `bm.to_mesh(me); bm.free()`).
- **`mesh.from_pydata(verts, edges, faces)`**: Quick mesh creation for prototyping. Call `mesh.validate(verbose=True)` afterward to catch invalid geometry that could crash Blender.

**Shape key data** is accessible through `ShapeKey.data[i].co` (per-vertex Vector) or via BMesh layers. For bulk access, use `foreach_get`:

```python
sk = obj.data.shape_keys.key_blocks["Key 1"]
coords = np.empty(len(sk.data) * 3, dtype=np.float32)
sk.data.foreach_get("co", coords)
```

**Vertex group weights** lack `foreach_get`/`foreach_set` support — this is a known API limitation. The three access patterns are: `VertexGroup.weight(index)` (throws RuntimeError if vertex isn't in the group), iterating `MeshVertex.groups` for per-vertex group elements, or BMesh's deform layer (`bm.verts.layers.deform`).

To access **post-modifier mesh data**, use the evaluated depsgraph:

```python
depsgraph = bpy.context.evaluated_depsgraph_get()
obj_eval = obj.evaluated_get(depsgraph)
mesh_eval = obj_eval.data  # Modifiers applied
```

For a persistent copy, use `bpy.data.meshes.new_from_object(obj_eval, preserve_all_data_layers=True, depsgraph=depsgraph)`. Without `preserve_all_data_layers=True`, vertex groups get stripped.

**Normals API changed significantly in 4.1**: `auto_smooth_angle`, `calc_normals_split()`, and `MeshLoop.normal` write access were all removed. Use `Mesh.corner_normals` (auto-updating read-only collection) and `normals_split_custom_set()` for custom normals.

---

## 6. Performance hinges on eliminating per-vertex Python loops

The **`foreach_get`/`foreach_set` methods are approximately 7× faster** than Python loops for mesh data transfer. They copy data directly between Blender's C structures and flat contiguous buffers, minimizing Python/C boundary crossings. Benchmarks show ~13.8 million vertex coordinates per second via foreach_get versus ~1.87 million through naive Python iteration.

The recommended pattern combines foreach with NumPy for vectorized processing:

```python
import numpy as np

mesh = obj.data
n = len(mesh.vertices)

# Export to NumPy
coords = np.empty(n * 3, dtype=np.float32)
mesh.vertices.foreach_get("co", coords)
coords = coords.reshape(-1, 3)

# Vectorized processing — no Python loops
coords += np.array([1.0, 0.0, 0.0])  # Translate all vertices

# Import back
mesh.vertices.foreach_set("co", coords.reshape(-1))
mesh.update()
```

Use `np.empty()` over `np.zeros()` to avoid unnecessary initialization. Always flatten arrays before `foreach_set()`. Use `dtype=np.float32` for coordinates to match Blender's internal representation. Note that **Blender 5.0 changed `mathutils.Vector` to float32** (from float64), which affects numerical precision in direct calculations.

For **meshes exceeding 50K vertices**, prefer `foreach_set` over `from_pydata()` for creation — `from_pydata` is 2–4× slower due to validation overhead. Blender's own codebase uses this pattern internally: the `Mesh.edge_keys` property was sped up **6–13×** by switching to foreach_get + NumPy.

One important exception: **sparse operations** affecting a small fraction of vertices (such as facial shape keys touching 661 out of 25,000 vertices) may be faster with a targeted Python loop over only affected indices rather than copying the entire array. The Diffeomorphic Daz Importer implements a configurable threshold to choose between methods, achieving roughly 2× overall import speedup.

BMesh carries **significant per-element Python overhead** and uses double memory (both the Mesh and BMesh representations exist simultaneously). Reserve it for topology operations where its `bmesh.ops` are genuinely needed.

---

## 7. Blender 5.0 and 5.1 introduced specific breaking API changes

**Blender 5.0** (November 2025) brought several changes that break existing add-ons:

- **Property storage separation**: `bpy.props`-defined properties are no longer accessible via dict syntax (`obj['prop']`). This is the most impactful change — any code using bracket notation to access RNA properties must switch to attribute access.
- **Legacy Action API removed**: `action.fcurves`, `action.groups`, and `action.id_root` are gone. Use the new Action API introduced in 4.4 with `channelbag.fcurves` and `action.fcurve_ensure_for_datablock()`.
- **Grease Pencil renamed to Annotations**: `bpy.types.GreasePencil` → `bpy.types.Annotation`, `bpy.data.grease_pencils` → `bpy.data.annotations`.
- **`Image.bindcode` removed**: Use `gpu.texture.from_image(image)` instead.
- **mathutils Vector now float32**: Previously float64. This can affect numerical precision in calculations and changes behavior when converting to/from NumPy arrays.
- **Compositor node renames**: Many compositor-specific nodes replaced by shader node counterparts (e.g., `CompositorNodeGamma` → `ShaderNodeGamma`).
- **Bundled modules made private**: `bl_console_utils`, `bl_rna_utils`, and other internal modules must not be used by add-ons.

**Blender 5.1** (current release, April 2026) upgraded to **Python 3.13** (VFX Platform 2026), deprecated the `columns` parameter of `UILayout.template_list`, and added `bpy.app.cachedir`. Node Tools now require a globally unique `idname`.

**Blender 5.2** (in development) adds `gpu.init()` for background-mode GPU initialization and annotation stroke removal APIs.

---

## 8. Collection and object management should favor bpy.data over bpy.ops

Always use `bpy.data` APIs for creating and managing data blocks. Operators (`bpy.ops`) depend on context, return only status sets, and can fail silently. The `bpy.data` path returns created objects directly and works regardless of UI state:

```python
# Create collection, link to scene
collection = bpy.data.collections.new("MyCollection")
bpy.context.scene.collection.children.link(collection)

# Create mesh and object
mesh = bpy.data.meshes.new("MyMesh")
mesh.from_pydata(vertices, edges, faces)
mesh.validate(verbose=True)
mesh.update()

obj = bpy.data.objects.new("MyObject", mesh)
collection.objects.link(obj)
```

Check for existing data before creating duplicates: `collection = bpy.data.collections.get("Name") or bpy.data.collections.new("Name")`.

**Orphan data blocks** (zero users) are purged on save/reload. They commonly occur when deleting objects without removing their mesh data. Clean up properly:

```python
mesh = obj.data
bpy.data.objects.remove(obj)
if mesh and mesh.users == 0:
    bpy.data.meshes.remove(mesh)
```

Or use `bpy.data.orphans_purge(do_recursive=True)` for bulk cleanup. Set `use_fake_user = True` on data blocks that should survive with zero real users.

For **depsgraph updates**, call `bpy.context.view_layer.update()` after programmatic changes to ensure the dependency graph recalculates. Be cautious with `depsgraph_update_post` handlers — they fire on every dependency graph update and can create infinite loops if the handler itself modifies data.

---

## 9. Extension packaging requires manifest, relative imports, and self-containment

A properly structured multi-file extension looks like this:

```
my_addon-1.0.0.zip
├── blender_manifest.toml
├── __init__.py
├── operators/
│   ├── __init__.py
│   └── core_ops.py
├── panels/
│   ├── __init__.py
│   └── sidebar.py
└── properties/
    ├── __init__.py
    └── scene_props.py
```

The top-level `__init__.py` uses relative imports and supports module reload:

```python
if "bpy" in locals():
    import importlib
    importlib.reload(operators)
    importlib.reload(panels)
else:
    from . import operators, panels

import bpy

def register():
    operators.register()
    panels.register()

def unregister():
    panels.unregister()
    operators.unregister()
```

**Extension platform requirements** for `extensions.blender.org` are strict:

- All imports must be relative — no absolute imports for internal modules
- Extensions must not write to their own directory; use `bpy.utils.extension_path_user(__package__, create=True)` for writable storage
- External Python dependencies must be bundled as `.whl` files in the package, not installed via pip at runtime
- Network access must respect `bpy.app.online_access`
- No `sys.path` manipulation or modification of other add-ons
- Permissions (`files`, `network`, `clipboard`, `camera`, `microphone`) must be declared accurately in the manifest

Build with `blender --command extension build`, validate with `blender --command extension validate`, and test locally via Install from Disk in preferences.

---

## 10. Common pitfalls that break add-ons across versions

**Context overrides changed completely in 4.0**. The old dict-passing pattern (`bpy.ops.some_op({"area": area})`) was deprecated in 3.2 and removed in 4.0. Use `context.temp_override()`:

```python
with bpy.context.temp_override(window=window, area=area):
    bpy.ops.view3d.some_operator()
```

**Handler accumulation** is a silent bug: appending a handler in `register()` without removing it in `unregister()` causes duplicates on every add-on reload. Always track handler references and clean up. Use the `@persistent` decorator for handlers that must survive file loads.

**`depsgraph_update_post` infinite loops** occur when a handler modifies data, triggering another update that calls the handler again. Guard against this with flags or by checking `depsgraph.updates` to verify relevant data actually changed.

**`bpy.context` at module level fails silently**: context is unavailable at import time. All context access must occur inside functions or methods, never at the top level of a module.

**`bl_options = {'REGISTER', 'UNDO'}` omission** is a frequent crash source. Any operator modifying Blender data without `'UNDO'` corrupts the undo stack. Always include it.

**Property namespace collisions** are global — `bpy.types.Scene.my_prop` will conflict if two add-ons use the same name. Use unique prefixes based on your add-on's identifier. Similarly, `bl_idname` values must be globally unique; the naming convention (`ADDON_OT_name`) helps prevent conflicts.

**Version-specific API breaks** follow a pattern: major Blender releases (2.80, 3.0, 4.0, 5.0) introduce breaking changes, while minor releases within an LTS cycle (4.2.x) maintain backward compatibility. Target `blender_version_min` to an LTS release and test against the next major version before it ships. The Blender Developer release notes at `developer.blender.org/docs/release_notes/` document every Python API change and are the authoritative source for migration work.

---

## Conclusion

Building durable Blender 5 add-ons comes down to a few high-leverage practices. First, adopt the extension system with `blender_manifest.toml` and relative imports — this is the future and unlocks the Extensions Platform. Second, respect the Blender 5.0 property storage separation by never using dict-style access for RNA properties. Third, eliminate per-vertex Python loops by using `foreach_get`/`foreach_set` with NumPy for any mesh operations beyond trivial sizes. Fourth, favor `bpy.data` over `bpy.ops` for all programmatic data creation and management. And fifth, treat `register()`/`unregister()` as contracts — register in dependency order, unregister in reverse, and clean up every handler, timer, and custom property. The add-ons that survive across versions are those built on these fundamentals rather than shortcuts that happen to work in one release.