from meshlib import mrmeshpy as mm
from pathlib import Path
import sys
from typing import List, Tuple


def cleanup_mesh(input_mesh_path: str, output_mesh_path: str = None, verbose: bool = True) -> str:
    """Clean up a mesh using MeshLib.
    
    Operations performed:
    - Fix degenerate faces
    - Fix multiple edges
    - Fix creases
    
    Args:
        input_mesh_path: Path to the input mesh file
        output_mesh_path: Path to save the cleaned mesh (optional, auto-generated if not provided)
        verbose: Print status messages
        
    Returns:
        Path to the output mesh file
    """
    input_path = Path(input_mesh_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input mesh not found: {input_mesh_path}")
    
    if verbose:
        print(f"Loading mesh from: {input_mesh_path}")
    
    # Load the mesh
    mesh = mm.loadMesh(str(input_path))
    
    if verbose:
        print(f"  Mesh loaded: {mesh.topology.vertSize()} vertices, {mesh.topology.faceSize()} faces")
    
    # Perform cleanup operations
    if verbose:
        print("Fixing mesh degeneracies...")
    degenerate_params = mm.FixMeshDegeneraciesParams()
    mm.fixMeshDegeneracies(mesh, degenerate_params)
    
    if verbose:
        print("Fixing multiple edges...")
    mm.fixMultipleEdges(mesh)
    
    if verbose:
        print("Fixing creases...")
    crease_params = mm.FixCreasesParams()
    mm.fixMeshCreases(mesh, crease_params)
    
    # Generate output path if not provided
    if output_mesh_path is None:
        stem = input_path.stem
        suffix = input_path.suffix
        output_mesh_path = str(input_path.parent / f"{stem}_cleaned{suffix}")
    
    if verbose:
        print(f"\nMesh cleanup complete!")
        print(f"  Final mesh: {mesh.topology.vertSize()} vertices, {mesh.topology.faceSize()} faces")
        print(f"Saving cleaned mesh to: {output_mesh_path}")
    
    # Save the cleaned mesh
    mm.saveMesh(mesh, str(output_mesh_path))
    
    if verbose:
        print("Done!")
    
    return output_mesh_path


def cleanup_batch(folder_path: str, output_folder: str = None, verbose: bool = True) -> Tuple[int, int, List[str]]:
    """Clean up all mesh files in a folder.
    
    Args:
        folder_path: Path to folder containing mesh files
        output_folder: Path to save cleaned meshes (optional, uses folder_path if not provided)
        verbose: Print status messages
        
    Returns:
        Tuple of (successful_count, failed_count, list_of_output_paths)
    """
    folder = Path(folder_path)
    
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Folder not found or not a directory: {folder_path}")
    
    # Supported mesh file extensions
    mesh_extensions = {'.obj', '.stl', '.ply', '.gltf', '.glb', '.fbx', '.dae', '.3ds'}
    
    # Find all mesh files
    mesh_files = []
    for ext in mesh_extensions:
        mesh_files.extend(folder.glob(f"*{ext}"))
        mesh_files.extend(folder.glob(f"*{ext.upper()}"))
    
    if not mesh_files:
        print(f"No mesh files found in: {folder_path}")
        return 0, 0, []
    
    mesh_files = sorted(set(mesh_files))  # Remove duplicates and sort
    
    if verbose:
        print(f"\nFound {len(mesh_files)} mesh file(s) to process:")
        for i, f in enumerate(mesh_files, 1):
            print(f"  {i}. {f.name}")
        print()
    
    # Determine output folder
    if output_folder is None:
        output_folder = str(folder / "cleaned")
    
    output_path = Path(output_folder)
    output_path.mkdir(exist_ok=True, parents=True)
    
    successful = 0
    failed = 0
    output_paths = []
    
    # Process each mesh
    for i, mesh_file in enumerate(mesh_files, 1):
        try:
            if verbose:
                print(f"[{i}/{len(mesh_files)}] Processing: {mesh_file.name}")
            
            output_mesh = str(output_path / f"{mesh_file.stem}_cleaned{mesh_file.suffix}")
            result = cleanup_mesh(str(mesh_file), output_mesh, verbose=False)
            output_paths.append(result)
            successful += 1
            
            if verbose:
                print(f"  [OK] Saved to: {Path(result).name}\n")
        
        except Exception as e:
            failed += 1
            if verbose:
                print(f"  [FAIL] Error: {e}\n")
    
    if verbose:
        print("\n" + "="*60)
        print(f"Batch processing complete!")
        print(f"  Successful: {successful}/{len(mesh_files)}")
        print(f"  Failed: {failed}/{len(mesh_files)}")
        print(f"  Output folder: {output_folder}")
        print("="*60)
    
    return successful, failed, output_paths


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single file:  python mesh_cleanup.py <input_mesh> [output_mesh]")
        print("  Batch mode:   python mesh_cleanup.py --batch <folder> [output_folder]")
        print("\nExamples:")
        print("  python mesh_cleanup.py model.obj")
        print("  python mesh_cleanup.py model.obj cleaned_model.obj")
        print("  python mesh_cleanup.py --batch ./meshes ./cleaned_meshes")
        sys.exit(1)
    
    # Check for batch mode
    if sys.argv[1] == '--batch':
        if len(sys.argv) < 3:
            print("Error: Batch mode requires a folder path")
            print("Usage: python mesh_cleanup.py --batch <folder> [output_folder]")
            sys.exit(1)
        
        input_folder = sys.argv[2]
        output_folder = sys.argv[3] if len(sys.argv) > 3 else None
        
        try:
            successful, failed, outputs = cleanup_batch(input_folder, output_folder)
            sys.exit(0 if failed == 0 else 1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    else:
        # Single file mode
        input_mesh = sys.argv[1]
        output_mesh = sys.argv[2] if len(sys.argv) > 2 else None
        
        try:
            result = cleanup_mesh(input_mesh, output_mesh)
            print(f"\nCleaned mesh saved to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)