"""
Transition curve functions and vertex weight mirroring.
All curve functions: t in [0, 1] -> float in [0, 1].
"""

import numpy as np

from ..utils.mesh_utils import get_vertex_positions, get_vertex_group_weights

try:
    from mathutils.kdtree import KDTree
except ImportError:  # outside Blender (unit tests)
    KDTree = None


def apply_curve(t: np.ndarray, curve_type: str) -> np.ndarray:
    """
    Apply a named transition curve to array t (clamped to [0,1]).

    Every curve satisfies f(1 - t) == 1 - f(t) (point symmetry around 0.5).
    The center line relies on this so that the L and R splits are exact mirror
    images of each other while still summing to 1.
    """
    t = np.clip(t, 0.0, 1.0).astype(np.float32)

    if curve_type == 'LINEAR':
        return t

    elif curve_type == 'SMOOTH':
        # Smoothstep: 3t² - 2t³
        return 3.0 * t ** 2 - 2.0 * t ** 3

    elif curve_type == 'BELL':
        # Double smoothstep — creates a sharper S-curve than SMOOTH
        s = 3.0 * t ** 2 - 2.0 * t ** 3
        return 3.0 * s ** 2 - 2.0 * s ** 3

    elif curve_type in ('EASE_IN', 'EASE_OUT'):
        # Cubic ease measured outwards from the seam (u = 0 at X=0, 1 at the
        # zone edge), mirrored to both sides so symmetry is kept.
        #   EASE_IN:  weights stay near 50/50 at the seam, change fast at the edges
        #   EASE_OUT: weights change fast at the seam, settle softly at the edges
        u = np.abs(2.0 * t - 1.0)
        g = u ** 3 if curve_type == 'EASE_IN' else 1.0 - (1.0 - u) ** 3
        return 0.5 + 0.5 * np.sign(2.0 * t - 1.0) * g

    elif curve_type == 'EASE_IN_OUT':
        # Standard cubic ease: uses t² for first half, mirrors for second
        return np.where(t < 0.5, 2.0 * t ** 2, 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0)

    # Fallback
    return t


def build_symmetry_map(
    coords: np.ndarray,
    center_threshold: float = 0.001,
    search_tolerance: float = None,
) -> dict:
    """
    Build a dict mapping left vertex indices to right vertex indices.

    Args:
        coords: (N, 3) float32 array of vertex positions in local space.
        center_threshold: Vertices within this distance of X=0 are excluded.
        search_tolerance: Max distance for a mirror match (defaults to
                          center_threshold * 10).

    Returns:
        {left_idx: right_idx}  — only matched pairs are included.
    """
    if search_tolerance is None:
        search_tolerance = center_threshold * 10.0

    x = coords[:, 0]
    left_idx = np.where(x < -center_threshold)[0]
    right_idx = np.where(x > center_threshold)[0]

    if len(left_idx) == 0 or len(right_idx) == 0:
        return {}

    mirrored = coords[left_idx].copy()
    mirrored[:, 0] *= -1.0
    sym_map = {}

    if KDTree is not None:
        tree = KDTree(len(right_idx))
        for i, ri in enumerate(right_idx):
            tree.insert(coords[ri], i)
        tree.balance()
        for li, co in zip(left_idx, mirrored):
            _co, i, dist = tree.find(co)
            if i is not None and dist <= search_tolerance:
                sym_map[int(li)] = int(right_idx[i])
        return sym_map

    # Brute-force fallback (only used outside Blender)
    right_coords = coords[right_idx]
    for li, co in zip(left_idx, mirrored):
        diffs = right_coords - co
        sq_dists = np.einsum('ij,ij->i', diffs, diffs)
        best = int(np.argmin(sq_dists))
        if np.sqrt(sq_dists[best]) <= search_tolerance:
            sym_map[int(li)] = int(right_idx[best])

    return sym_map


def mirror_weights_left_to_right(
    obj,
    vertex_group_name: str,
    center_threshold: float = 0.001,
) -> tuple:
    """
    Copy vertex group weights from left-side verts to their right-side mirrors.
    Right-side verts whose mirror has no weight are removed from the group.

    Returns:
        (mirrored_count: int, warnings: list[str])
    """
    vg = obj.vertex_groups.get(vertex_group_name)
    if vg is None:
        return 0, [f"Vertex group '{vertex_group_name}' not found"]

    coords = get_vertex_positions(obj.data)
    weights = get_vertex_group_weights(obj, vertex_group_name)

    sym_map = build_symmetry_map(coords, center_threshold)
    warnings = []

    unweighted = []
    for left_idx, right_idx in sym_map.items():
        w = float(weights[left_idx])
        if w > 0.0:
            vg.add([right_idx], w, 'REPLACE')
        else:
            unweighted.append(right_idx)
    if unweighted:
        vg.remove(unweighted)

    n_left = int(np.sum(coords[:, 0] < -center_threshold))
    unmatched = n_left - len(sym_map)
    if unmatched > 0:
        warnings.append(
            f"{unmatched} left-side vert(s) in '{vertex_group_name}' have no mirror counterpart"
        )

    return len(sym_map), warnings
