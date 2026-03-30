import trimesh
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.sparse import csr_matrix


INPUT_PATH = r'C:\Users\Zayd\OneDrive\Documents\IGEN430\savedRuns\texturedMesh_20260325_004845.obj'
OUTPUT_PATH = r'C:\Users\Zayd\OneDrive\Documents\IGEN430\savedRuns\watertightCleanedCropped_y10pDOG.obj'

def make_watertight_shrinkwrap(mesh, resolution=100):
    """
    Converts a messy, fractured mesh into a solid, watertight shell 
    using Voxelization and Marching Cubes.
    
    mesh: trimesh.Trimesh object
    resolution: How many voxels (3D pixels) across the longest dimension.
                Higher = more detail, but uses exponentially more RAM.
    """
    print("\n[SHRINKWRAP] Starting voxelization process...")
    
    # 1. Auto-calculate the voxel size based on the object's real scale
    max_dimension = max(mesh.extents)
    pitch = max_dimension / resolution
    print(f"[SHRINKWRAP] Object size: {max_dimension:.2f}. Voxel pitch: {pitch:.4f}")
    
    # 2. Convert the mesh into 3D pixels (Voxels)
    print(f"[SHRINKWRAP] Building {resolution}x{resolution}x{resolution} voxel grid...")
    voxel_grid = mesh.voxelized(pitch=pitch)
    
    # 3. Fill the inside of the voxel grid so it is completely solid
    print("[SHRINKWRAP] Filling internal voids...")
    solid_voxels = voxel_grid.fill()
    
    # 4. Extract a brand new, continuous outer mesh skin
    print("[SHRINKWRAP] Running Marching Cubes to extract new skin...")
    watertight_mesh = solid_voxels.marching_cubes
    
    # 5. Smooth the mesh (Marching Cubes can look slightly "blocky")
    print("[SHRINKWRAP] Smoothing the final surface...")
    trimesh.smoothing.filter_taubin(watertight_mesh, iterations=10)
    
    if watertight_mesh.is_watertight:
        print("[SHRINKWRAP] Success! The mesh is 100% watertight and manifold.")
    else:
        print("[SHRINKWRAP] Warning: The output is still not perfectly watertight.")
        
    return watertight_mesh

def connect_mesh_components(mesh, thickness_percentage=0.5, extra_connections=2):
    """
    Connects isolated components using a Minimum Spanning Tree PLUS extra 
    redundant connections to create a denser scaffolding web.
    
    thickness_percentage: The bridge radius as a % of the mesh's largest dimension.
    extra_connections: How many additional nearby pieces each component should connect to.
    """
    print("\n[BRIDGING] Splitting mesh into components...")
    components = mesh.split(only_watertight=False)
    num_comps = len(components)
    
    if num_comps <= 1:
        print("[BRIDGING] Mesh is already a single contiguous piece.")
        return mesh
        
    # --- AUTO-SCALING MATH ---
    max_dimension = np.max(mesh.extents)
    auto_radius = max_dimension * (thickness_percentage / 100.0)
    print(f"[BRIDGING] Mesh Max Dimension: {max_dimension:.4f} units")
    print(f"[BRIDGING] Auto-calculated bridge radius: {auto_radius:.6f} units")

    print(f"[BRIDGING] Found {num_comps} components. Calculating distance matrix...")

    trees = [cKDTree(comp.vertices) for comp in components]
    distances = np.zeros((num_comps, num_comps))
    closest_points = {}

    for i in range(num_comps):
        for j in range(i + 1, num_comps):
            dist, idx = trees[j].query(components[i].vertices)
            min_idx_i = np.argmin(dist)  
            min_idx_j = idx[min_idx_i]   
            min_dist = dist[min_idx_i]   
            
            distances[i, j] = min_dist
            distances[j, i] = min_dist
            
            p_i = components[i].vertices[min_idx_i]
            p_j = components[j].vertices[min_idx_j]
            closest_points[(i, j)] = (p_i, p_j)
            closest_points[(j, i)] = (p_j, p_i)

    print("[BRIDGING] Computing Minimum Spanning Tree...")
    graph = csr_matrix(distances)
    mst = minimum_spanning_tree(graph).toarray()

    # --- NEW LOGIC: Collect all edges to build ---
    edges_to_build = set()

    # 1. Add the baseline MST edges (Guarantees everything is linked)
    for i in range(num_comps):
        for j in range(num_comps):
            if mst[i, j] > 0:
                edge = tuple(sorted((i, j))) # Sort to prevent duplicate A->B and B->A
                edges_to_build.add(edge)

    # 2. Add the extra dense connections
    if extra_connections > 0:
        print(f"[BRIDGING] Adding {extra_connections} extra connections per component...")
        for i in range(num_comps):
            # Sort the distances for component 'i' from shortest to longest
            row = distances[i, :]
            sorted_indices = np.argsort(row)
            
            added = 0
            for j in sorted_indices:
                if i == j: 
                    continue # Skip itself
                
                edge = tuple(sorted((i, j)))
                # If this connection doesn't exist yet, add it
                if edge not in edges_to_build:
                    edges_to_build.add(edge)
                    added += 1
                    if added >= extra_connections:
                        break # Move to the next component once we hit our quota

    print(f"[BRIDGING] Building {len(edges_to_build)} total 3D bridges...")
    bridges = []
    for (i, j) in edges_to_build:
        p1, p2 = closest_points[(i, j)]
        bridge = trimesh.creation.cylinder(radius=auto_radius, segment=(p1, p2))
        bridges.append(bridge)

    print("[BRIDGING] Merging original components and bridges into final mesh...")
    final_mesh = trimesh.util.concatenate(components + bridges)
    
    print("[BRIDGING] Success! Scaffold complete.")
    return final_mesh

# def remove_small_components(mesh, min_faces, min_area):

#     # Removes components with few faces or small area to destroy thin/thin parts.
#     # mesh: trimesh.Trimesh object
#     # min_faces: Minimum number of faces to keep a component
#     # min_area: Minimum area of a component to keep

#     # Split mesh into connected components
#     components = mesh.split(only_watertight=False)

    
#     kept_components = []
#     for comp in components:
#         # Keep components with enough faces or area
#         if len(comp.faces) > min_faces or comp.area > min_area:
#             kept_components.append(comp)
    
#     # kept_components = max(components, key=lambda c: len(c.faces))

#     # Recombine remaining components
#     if len(kept_components) > 0:
#         return trimesh.util.concatenate(kept_components)
#     else:
#         return None

def clean_and_fill_mesh(mesh, keep_top_n=15, min_faces=50):
    """
    Cleans a fractured mesh by keeping the largest N components, 
    and deleting microscopic floating noise.
    
    mesh: trimesh.Trimesh object
    keep_top_n: The number of largest disconnected pieces to keep (e.g., 10-20).
    min_faces: An absolute minimum face count to prevent keeping actual noise.
    """
    print("\n[CLEANUP] Splitting mesh into connected components...")
    
    # Split mesh into separate disconnected pieces
    components = mesh.split(only_watertight=False)
    
    if not components:
        print("[ERROR] No components found in mesh.")
        return None

    print(f"[CLEANUP] Found {len(components)} total disconnected pieces.")

    # Sort all components from largest to smallest based on face count
    components.sort(key=lambda c: len(c.faces), reverse=True)
    
    kept_components = []
    
    # Grab the top N largest pieces, as long as they meet the bare minimum size
    for comp in components[:keep_top_n]:
        if len(comp.faces) >= min_faces:
            kept_components.append(comp)

    if not kept_components:
        print("[WARNING] All components were filtered out! Try lowering min_faces.")
        return None

    print(f"[CLEANUP] Kept the {len(kept_components)} largest pieces.")

    # Recombine the surviving pieces
    cleaned_mesh = trimesh.util.concatenate(kept_components)

    # Attempt to fill holes
    print("[CLEANUP] Filling holes in the mesh...")
    try:
        # trimesh.fill_holes() modifies the mesh in-place
        trimesh.repair.fill_holes(cleaned_mesh) 

        # If the mesh was completely closed, it becomes watertight
        if cleaned_mesh.is_watertight:
            print("[CLEANUP] Success! The mesh is now completely watertight.")
        else:
            print("[CLEANUP] Holes filled, but mesh is still not 100% watertight (complex gaps may remain).")
            
    except Exception as e:
        print(f"[WARNING] Hole filling encountered an issue: {e}")

    return cleaned_mesh
    
def crop_mesh_bottom_y(mesh, crop_percentage=5.0):

    # Crops the bottom percentage of the mesh using y-axis as vertical.
    
    # mesh: trimesh.Trimesh object
    # crop_percentage: How much of the bottom to remove (e.g., 5.0 means 5%).
    
    # Returns: Cropped trimesh.Trimesh object or None if error.

    if not isinstance(mesh, trimesh.Trimesh):
        print("[ERROR] Input must be a trimesh.Trimesh object.")
        return None

    axis_idx = 1  # y-axis

    # Find the lowest and highest points of the mesh on the y-axis
    min_val = mesh.bounds[0][axis_idx]
    max_val = mesh.bounds[1][axis_idx]
    
    # Calculate the exact height coordinate where the cut will happen
    total_height = max_val - min_val
    cut_height = min_val + (total_height * (crop_percentage / 100.0))
    
    print(f"[CROP] Mesh height on y-axis: {total_height:.2f} units.")
    print(f"[CROP] Slicing off the bottom {crop_percentage}%...")

    # Define the cutting plane
    # Normal [0, 1, 0] means keep everything ABOVE the cut on the Y axis
    plane_normal = [0.0, 1.0, 0.0]
    plane_origin = [0.0, cut_height, 0.0]

    # Execute the slice
    sliced_mesh = mesh.slice_plane(plane_origin=plane_origin, plane_normal=plane_normal)
    
    print("[CROP] Cropping done!")
    return sliced_mesh

# Load mesh
mesh = trimesh.load(INPUT_PATH)

# Crop mesh bottom using y-axis
cropped_mesh = crop_mesh_bottom_y(mesh, crop_percentage=10.0)

if cropped_mesh:
    cropped_mesh.export(OUTPUT_PATH+"cropped.obj")
#     print(f"Cropped mesh saved to {OUTPUT_PATH}.")

# Clean mesh
# cleaned_mesh = remove_small_components(cropped_mesh if 'cropped_mesh' in locals() else mesh, min_faces=100, min_area=0.01)
cleaned_mesh = clean_and_fill_mesh(cropped_mesh if 'cropped_mesh' in locals() else mesh, keep_top_n=50, min_faces=50)

final_mesh = connect_mesh_components(cleaned_mesh if 'cleaned_mesh' in locals() else cropped_mesh if 'cropped_mesh' in locals() else mesh, thickness_percentage=0.5, extra_connections=3)

# if final_mesh:
#     final_mesh.export(OUTPUT_PATH)

watertight_mesh = make_watertight_shrinkwrap(final_mesh if 'final_mesh' in locals() else cleaned_mesh if 'cleaned_mesh' in locals() else cropped_mesh if 'cropped_mesh' in locals() else mesh, resolution=200)

if watertight_mesh:
    watertight_mesh.export(OUTPUT_PATH)