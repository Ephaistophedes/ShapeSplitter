"""
Center line vertex classification and L/R weight computation.
"""

import numpy as np
from . import weights as weights_mod


def compute_centerline_weights(
    x_coords: np.ndarray,
    blend_width: float,
    transition_type: str,
    center_threshold: float = 0.0,
) -> tuple:
    """
    Compute per-vertex L and R weights from the center line settings.

    The transition zone is centered on X=0 and spans [-blend_width/2, +blend_width/2]:
      x <= -blend_width/2          → weight_L = 1.0  (fully left)
      x >= +blend_width/2          → weight_L = 0.0  (fully right)
      otherwise                    → weight_L = 1.0 - curve(t)
          where t = (x + blend_width/2) / blend_width
      |x| <= center_threshold      → weight_L = 0.5  (seam verts split evenly)

    weight_R is always 1.0 - weight_L, and because every curve is point-symmetric
    weight_R(x) == weight_L(-x), so the two splits are exact mirror images.

    Args:
        x_coords:         (N,) float32 array of per-vertex X positions in local space.
        blend_width:      Full width of the transition zone.
        transition_type:  One of LINEAR | SMOOTH | BELL | EASE_IN | EASE_OUT | EASE_IN_OUT.
        center_threshold: Verts this close to X=0 are forced to an exact 50/50 split.

    Returns:
        (weight_L, weight_R): two (N,) float32 arrays.
    """
    x_coords = np.asarray(x_coords, dtype=np.float32)

    if blend_width > 0.0:
        t = (x_coords + blend_width * 0.5) / blend_width
        weight_L = (1.0 - weights_mod.apply_curve(t, transition_type)).astype(np.float32)
    else:
        weight_L = np.where(x_coords < 0.0, 1.0, 0.0).astype(np.float32)

    weight_L[np.abs(x_coords) <= center_threshold] = 0.5

    weight_R = 1.0 - weight_L

    return weight_L, weight_R
