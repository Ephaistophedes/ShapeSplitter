# Known issues and limitations

The bugs found in the v1.0.0 review are fixed in 1.1.0 (see `CHANGELOG.md`). Still open:

- **The split uses local-space X.** Scale and rotation are not taken into account, and the
  panel only warns about unapplied scale. The mesh must be symmetric around its local
  X = 0.
- **Output names are lowercased from the mask display name.** `Eye_L` gives `smile_eye_l`.
  Renaming a mask inline in the list does not rename its vertex group; the rename button does.
- **Preview does not refresh while you paint weights.** Change any preview setting or run
  Mirror Weights to refresh it.
- **Reading vertex group weights is a Python loop over all vertices**, because Blender has no
  bulk `foreach_get` for vertex groups. It now runs once per mask per batch.
