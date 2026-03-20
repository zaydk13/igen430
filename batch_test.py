import subprocess
import os
import time
import sys
import json
import shutil
from datetime import datetime

# --- Configuration ---

# 1. Path to the Meshroom Batch Executable
MESHROOM_BIN = r"C:\Users\Zayd\OneDrive\Documents\Meshroom-2025.1.0-Windows\Meshroom-2025.1.0\meshroom_batch.exe"
# Automatically locate the compute executable in the same folder
COMPUTE_BIN = os.path.join(os.path.dirname(MESHROOM_BIN), "meshroom_compute.exe")

# 2. Where the RPi is dropping the images
# INPUT_IMAGES_DIR = r"Z:\Documents\igen430\image_send"
# INPUT_IMAGES_DIR = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\image_send"
# INPUT_IMAGES_DIR = r"C:\Users\Zayd\OneDrive\Documents\VSCode\IGEN430\images_20251126_140652"
INPUT_IMAGES_DIR = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\compressed_frames(50)"

# 3. Where you want the 3D model (OBJ file) to end up
OUTPUT_DIR = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\outputMesh"

# 4. Path to save the Meshroom Project File (.mg)
PROJECT_FILE = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\outputProjectFile\automated_project.mg"

# 4b. Save folder for archived project files and meshes with timestamps
SAVE_DIR = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\savedRuns"

# 5. How many images to wait for before starting
EXPECTED_IMAGES = 50

# 6. NEW OVERRIDE METHOD: Dictionary of node types and their settings
# This will inject directly into the .mg JSON file, bypassing CLI errors.
NODE_OVERRIDES = {
    "CameraInit": {
        "defaultFieldOfView": 45.0,
        # "width": "640",
        # "height": "480"
    },
    # "FeatureExtraction": {
    #     "describerTypes": "sift,akaze",
    #     "describerPreset": "high",
    #     "minRequired2DMotion": 3.0
    # },
    # "FeatureMatching": {
    #     "describerTypes": "sift,akaze",
    #     "distanceRatio": 0.8,
    #     "maxIteration": 2048
    # },
    # "StructureFromMotion": {
    #     "describerTypes": "sift,akaze",
    #     "minAngleInitialPair": 2.0,      # Default is 5.0. Allows video frames to start the 3D build.
    #     "minAngleForTriangulation": 1.0, # Default is 2.0. Allows tiny camera movements to generate 3D points.
    #     "minAngleForLandmark": 1.0         # Helps keep tracking points alive
    # },
    # "DepthMap": {
    # "downscale": 1  # Default is 2. Setting it to 1 forces full resolution.
    # },
    # "DepthMapFilter": {
    #     "minConsistentViews": 2 # Keeps points alive even if seen in fewer frames
    # },
    # # "MeshFiltering": {
    # #     "keepLargestMeshOnly": "True"
    # # }
    # "Meshing": {
    #     "estimateSpaceFromSfM": "False",
    #     "minAngleThreshold": 0.5,
    #     "maxAngleThreshold": 360.0
    # }
}

def save_run_with_timestamp():
    """Copy the completed project file and mesh to save folder with timestamp."""
    try:
        # Create save directory if it doesn't exist
        os.makedirs(SAVE_DIR, exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Copy project file
        mesh_path = os.path.join(OUTPUT_DIR, "texturedMesh.obj")
        if os.path.exists(PROJECT_FILE):
            project_filename = f"automated_project_{timestamp}.mg"
            project_save_path = os.path.join(SAVE_DIR, project_filename)
            shutil.copy2(PROJECT_FILE, project_save_path)
            print(f"[INFO] Saved project file: {project_save_path}")
        else:
            print(f"[WARNING] Project file not found: {PROJECT_FILE}")
        
        # Copy mesh file if it exists
        if os.path.exists(mesh_path):
            mesh_filename = f"texturedMesh_{timestamp}.obj"
            mesh_save_path = os.path.join(SAVE_DIR, mesh_filename)
            shutil.copy2(mesh_path, mesh_save_path)
            print(f"[INFO] Saved mesh file: {mesh_save_path}")
            
            # Also copy associated MTL file if it exists
            mtl_path = os.path.join(OUTPUT_DIR, "texturedMesh.mtl")
            if os.path.exists(mtl_path):
                mtl_filename = f"texturedMesh_{timestamp}.mtl"
                mtl_save_path = os.path.join(SAVE_DIR, mtl_filename)
                shutil.copy2(mtl_path, mtl_save_path)
                print(f"[INFO] Saved material file: {mtl_save_path}")
        else:
            print(f"[WARNING] Mesh file not found: {mesh_path}")
    except Exception as e:
        print(f"[ERROR] Failed to save run files: {e}")

def patch_meshroom_project(project_path):
    """
    Opens the generated .mg file, finds the target nodes, and injects
    the custom parameters directly into the JSON graph.
    """
    print("\n[PATCH] Applying custom node overrides to the project file...")
    try:
        with open(project_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        graph = data.get("graph", {})
        overrides_applied = 0
        
        # Iterate through all nodes in the project graph
        for node_id, node_data in graph.items():
            node_type = node_data.get("nodeType")
            
            # If the node type matches our overrides dictionary, apply the settings
            if node_type in NODE_OVERRIDES:
                if "inputs" not in node_data:
                    node_data["inputs"] = {}
                    
                for param_key, param_val in NODE_OVERRIDES[node_type].items():
                    node_data["inputs"][param_key] = param_val
                    overrides_applied += 1
                    print(f"  -> Set [{node_type}] {param_key} = {param_val}")
                    
        # Save the modified JSON back to the file
        with open(project_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        print(f"[PATCH] Successfully applied {overrides_applied} custom parameters.\n")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to patch project file: {e}")
        return False

def run_meshroom_pipeline():
    print("\n" + "="*60)
    print("      STARTING MESHROOM PIPELINE")
    print("="*60)
    print(f"Project File: {PROJECT_FILE}")
    print("Note: This process is heavy and may take 20-60+ minutes.")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    project_dir = os.path.dirname(PROJECT_FILE)
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)

    # --- STEP 1: Generate the base project file ---
    print("[INIT] Generating default project pipeline...")
    init_cmd = [
        MESHROOM_BIN,
        "--input", INPUT_IMAGES_DIR,
        "--output", OUTPUT_DIR,
        "--save", PROJECT_FILE,
        "--toNode", "CameraInit"  # Stop immediately after building the graph
    ]
    
    try:
        init_result = subprocess.run(init_cmd, capture_output=True, text=True)
        if not os.path.exists(PROJECT_FILE):
            print("[ERROR] Failed to generate base project file.")
            print(init_result.stderr)
            return False
    except Exception as e:
        print(f"[ERROR] Initialization failed: {e}")
        return False

    # --- STEP 2: Inject custom parameters ---
    if NODE_OVERRIDES:
        success = patch_meshroom_project(PROJECT_FILE)
        if not success:
            return False

    # --- STEP 3: Compute the patched project ---
    print("[COMPUTE] Starting full pipeline computation...")
    compute_cmd = [
        COMPUTE_BIN,
        PROJECT_FILE,
        "--forceCompute"
    ]

    pipeline_nodes = [
        "CameraInit", "FeatureExtraction", "ImageMatching", "FeatureMatching",
        "StructureFromMotion", "PrepareDenseScene", "DepthMap", 
        "DepthMapFilter", "Meshing", "MeshFiltering", "Texturing"
    ]

    process = None
    try:
        start_time = time.time()
        process = subprocess.Popen(
            compute_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1
        )

        current_stage = "Initialization"
        
        # Read the output line by line
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            # Identify if we moved to a new major node
            is_stage_header = False
            for node in pipeline_nodes:
                if f"[{node}]" in line or node in line:
                    if node != current_stage:
                        current_stage = node
                        print(f"\n---> Running Stage: {current_stage.upper()}")
                        is_stage_header = True
            
            # Print ALL Meshroom output
            if not is_stage_header:
                print(f"    [Meshroom] {line}")

        process.wait()
        end_time = time.time()
        duration = (end_time - start_time) / 60
    
        if process.returncode == 0:
            print("\n" + "="*60)
            print(f"SUCCESS! Meshroom run completed in {duration:.1f} minutes.")
            print(f"3D Model: {os.path.join(OUTPUT_DIR, 'texturedMesh.obj')}")
            print(f"Project File: {PROJECT_FILE}")
            print("="*60)

            save_run_with_timestamp()  # Save the project and mesh with a timestamp for record-keeping

            try:
                os.startfile(PROJECT_FILE)
            except Exception as e:
                print(f"[WARNING] Could not automatically open project file: {e}")
            return True
        else:
            print(f"\n[ERROR] Meshroom failed with return code {process.returncode}.")
            return False

    except KeyboardInterrupt:
        print("\n\n[INFO] Keyboard interrupt detected (Ctrl+C).")
        if process:
            print("[INFO] Terminating Meshroom process safely...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        return False
    except FileNotFoundError:
        print(f"\n[ERROR] Could not find meshroom executable at:\n{COMPUTE_BIN}")
        return False
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        return False

def monitor_folder():
    print(f"--- Meshroom Watchdog Active ---")
    print(f"Watching: {INPUT_IMAGES_DIR}")
    print(f"Waiting for {EXPECTED_IMAGES} images...")
    print("[INFO] Press Ctrl+C to stop watching.\n")
    
    try:
        while True:
            if os.path.exists(INPUT_IMAGES_DIR):
                files = [f for f in os.listdir(INPUT_IMAGES_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
                current_count = len(files)
                
                sys.stdout.write(f"\rCurrent count: {current_count}/{EXPECTED_IMAGES}")
                sys.stdout.flush()
                
                if current_count >= EXPECTED_IMAGES:
                    print("\n\nThreshold reached! Starting Meshroom pipeline...")
                    time.sleep(8) 
                    
                    run_meshroom_pipeline()
                    break 
            
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\n[INFO] Watchdog stopped by user.")

if __name__ == "__main__":
    monitor_folder()