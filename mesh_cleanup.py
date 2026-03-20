import trimesh
import numpy as np

def remove_small_components(mesh, min_faces, min_area):
    """
    Removes components with few faces or small area to destroy thin/thin parts.
    """

    # mesh.nondegenerate_faces()
    # mesh.remove_duplicate_faces()
    # mesh.remove_unreferenced_vertices()

    # Split mesh into connected components
    components = mesh.split(only_watertight=False)

    
    kept_components = []
    for comp in components:
        # Keep components with enough faces or area
        if len(comp.faces) > min_faces or comp.area > min_area:
            kept_components.append(comp)
    
    # kept_components = max(components, key=lambda c: len(c.faces))

    # Recombine remaining components
    if len(kept_components) > 0:
        return trimesh.util.concatenate(kept_components)
    else:
        return None

# Load mesh
mesh = trimesh.load(r'C:\Users\Zayd\OneDrive\Documents\IGEN430\savedRuns\texturedMesh_20260307_180407.obj')

# Clean mesh
cleaned_mesh = remove_small_components(mesh, min_faces=100, min_area=0.01)

if cleaned_mesh:
    cleaned_mesh.export(r'C:\Users\Zayd\OneDrive\Documents\IGEN430\savedRuns\cleaned1.obj')