"""
Center line vertex classification and L/R weight computation.
"""

import numpy as np
from . import weights as weights_mod


def compute_centerline_weights(
    x_coords: np.ndarray,
    blend_distance: float,
    blend_falloff: float,
    transition_type: str,
) -> tuple:
    """
    Compute per-vertex L and R weights from the center line settings.

    Weight rules (applied in order):
      x < -blend_distance                     → weight_L = 1.0  (fully left)
      x > blend_distance + blend_falloff      → weight_L = 0.0  (fully right)
      otherwise                               → weight_L = 1.0 - curve(t)
          where t = (x - (-blend_distance)) / blend_falloff, clamped [0, 1]

    weight_R is always 1.0 - weight_L.

    Args:
        x_coords:       (N,) float32 array of per-vertex X positions in local space.
        blend_distance: World-space distance from X=0 where blending starts.
        blend_falloff:  World-space distance of the transition zone.
        transition_type: One of LINEAR | SMOOTH | BELL | EASE_IN | EASE_OUT | EASE_IN_OUT.

    Returns:
        (weight_L, weight_R): two (N,) float32 arrays.
    """
    n = len(x_coords)
    weight_L = np.ones(n, dtype=np.float32)

    # Fully right: no left influence
    right_mask = x_coords > (blend_distance + blend_falloff)
    weight_L[right_mask] = 0.0

    # Transition zone (neither fully left nor fully right)
    transition_mask = (~right_mask) & (x_coords > -blend_distance)
    if np.any(transition_mask):
        t = (x_coords[transition_mask] - (-blend_distance)) / blend_falloff
        curve_vals = weights_mod.apply_curve(t, transition_type)
        weight_L[transition_mask] = 1.0 - curve_vals

    weight_R = 1.0 - weight_L

    return weight_L, weight_R
