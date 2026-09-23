"""
Transition curve functions and vertex weight mirroring.
All curve functions: t in [0, 1] -> float in [0, 1].
"""

import numpy as np


def apply_curve(t: np.ndarray, curve_type: str) -> np.ndarray:
    """Apply a named transition curve to array t (clamped to [0,1])."""
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

    elif curve_type == 'EASE_IN':
        return t ** 2

    elif curve_type == 'EASE_OUT':
        return 1.0 - (1.0 - t) ** 2

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
        Logs unmatched verts as a separate count (see return value).
    """
    if search_tolerance is None:
        search_tolerance = center_threshold * 10.0

    x = coords[:, 0]
    left_idx = np.where(x < -center_threshold)[0]
    right_idx = np.where(x > center_threshold)[0]

    if len(left_idx) == 0 or len(right_idx) == 0:
        return {}

    right_coords = coords[right_idx]  # (M, 3)
    sym_map = {}

    for li in left_idx:
        lv = coords[li]
        mirrored = np.array([-lv[0], lv[1], lv[2]], dtype=np.float32)

        diffs = right_coords - mirrored
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

    Returns:
        (mirrored_count: int, warnings: list[str])
    """
    mesh = obj.data
    vg = obj.vertex_groups.get(vertex_group_name)
    if vg is None:
        return 0, [f"Vertex group '{vertex_group_name}' not found"]

    n = len(mesh.vertices)
    raw = np.empty(n * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", raw)
    coords = raw.reshape(-1, 3)

    sym_map = build_symmetry_map(coords, center_threshold)
    warnings = []
    mirrored = 0

    for left_idx, right_idx in sym_map.items():
        try:
            w = vg.weight(left_idx)
        except RuntimeError:
            w = 0.0
        vg.add([right_idx], w, 'REPLACE')
        mirrored += 1

    n_left = int(np.sum(coords[:, 0] < -center_threshold))
    unmatched = n_left - len(sym_map)
    if unmatched > 0:
        warnings.append(
            f"{unmatched} left-side vert(s) in '{vertex_group_name}' have no mirror counterpart"
        )

    return mirrored, warnings
