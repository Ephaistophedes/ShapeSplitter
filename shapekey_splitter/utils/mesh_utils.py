"""
Vertex data helpers for mesh operations.
"""

import numpy as np


def get_vertex_positions(mesh) -> np.ndarray:
    """Return all vertex positions as (N, 3) float32 array (local space)."""
    n = len(mesh.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def get_shape_key_positions(sk) -> np.ndarray:
    """Return shape key vertex positions as (N, 3) float32 array."""
    n = len(sk.data)
    co = np.empty(n * 3, dtype=np.float32)
    sk.data.foreach_get("co", co)
    return co.reshape(-1, 3)


def get_vertex_group_weights(obj, vg_name: str) -> np.ndarray:
    """
    Return per-vertex weights for a vertex group as (N,) float32 array.
    Vertices not in the group are 0.0.
    Note: vertex groups have no foreach_get — iteration is unavoidable here.
    """
    n = len(obj.data.vertices)
    weights = np.zeros(n, dtype=np.float32)

    vg = obj.vertex_groups.get(vg_name)
    if vg is None:
        return weights

    vg_index = vg.index
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group == vg_index:
                weights[v.index] = g.weight
                break

    return weights


def check_scale_applied(obj) -> bool:
    """Return True if the object scale is approximately (1, 1, 1)."""
    s = obj.scale
    return abs(s[0] - 1.0) < 1e-3 and abs(s[1] - 1.0) < 1e-3 and abs(s[2] - 1.0) < 1e-3


def unique_name(base: str, existing: set) -> str:
    """Return base if not in existing, otherwise base_001, base_002, ..."""
    if base not in existing:
        return base
    i = 1
    while f"{base}_{i:03d}" in existing:
        i += 1
    return f"{base}_{i:03d}"
