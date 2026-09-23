if "bpy" in locals():
    import importlib
    from . import weights, centerline, splitter
    importlib.reload(weights)
    importlib.reload(centerline)
    importlib.reload(splitter)
else:
    from . import weights, centerline, splitter
