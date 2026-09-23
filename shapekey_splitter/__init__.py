"""
Shape Key Splitter — Blender 5 add-on.

Splits shape keys into directional (L/R) and region-masked variants using
painted vertex weights. Output is a collection of baked mesh objects suitable
for export to Unity / Unreal Engine as blendshapes.
"""

if "bpy" in locals():
    import importlib
    from . import data, core, operators, ui, utils
    importlib.reload(utils)
    importlib.reload(data)
    importlib.reload(core)
    importlib.reload(operators)
    importlib.reload(ui)
else:
    from . import data, core, operators, ui, utils

import bpy


def register():
    # data must come first — PropertyGroups must exist before operators/panels
    data.register()
    operators.register()
    ui.register()


def unregister():
    # Reverse order
    ui.unregister()
    operators.unregister()
    data.unregister()
