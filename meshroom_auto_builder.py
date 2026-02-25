import subprocess
import os
import time
import sys

# --- Configuration ---

# 1. Path to the Meshroom Batch Executable
MESHROOM_BIN = r"C:\Users\Zayd\OneDrive\Documents\Meshroom-2025.1.0-Windows\Meshroom-2025.1.0\meshroom_batch.exe"

# 2. Where the RPi is dropping the images
INPUT_IMAGES_DIR = r"Z:\Documents\igen430\image_send"

# 3. Where you want the 3D model (OBJ file) to end up
OUTPUT_DIR = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\outputMeshes"

# 4. Path to save the Meshroom Project File (.mg)
PROJECT_FILE = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\outputProjectFiles\automated_project.mg"

# 5. How many images to wait for before starting
EXPECTED_IMAGES = 50 

# 6. Advanced Overrides (Commented out for initial debugging)
# Note: Meshroom default pipelines append "_1" to node names.
NODE_OVERRIDES = {
    # "FeatureMatching_1.geometricEstimator": "acransac", 
    # "FeatureMatching_1.distanceRatio": 0.8,
    # "FeatureMatching_1.maxIteration": 50000,
    # "FeatureExtraction_1.describerTypes": "sift",
    # "FeatureExtraction_1.minRequired2DMotion": 3.0,
    # "MeshFiltering_1.keepLargestMeshOnly": "True"
}

def run_meshroom_pipeline():
    print("\n" + "="*60)
    print("      STARTING MESHROOM PIPELINE")
    print("="*60)
    print(f"Project File: {PROJECT_FILE}")
    print("Note: This process is heavy and may take 20-60+ minutes.")
    
    # Ensure all output directories exist before we start
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    project_dir = os.path.dirname(PROJECT_FILE)
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)

    # Stages to monitor in the console output
    pipeline_nodes = [
        "CameraInit", "FeatureExtraction", "ImageMatching", "FeatureMatching",
        "StructureFromMotion", "PrepareDenseScene", "DepthMap", 
        "DepthMapFilter", "Meshing", "MeshFiltering", "Texturing"
    ]

    # Construct the command.
    cmd = [
        MESHROOM_BIN,
        "--input", INPUT_IMAGES_DIR,
        "--output", OUTPUT_DIR,
        "--save", PROJECT_FILE,  
        "--forceCompute",        
    ]

    # Append Overrides if they exist
    if NODE_OVERRIDES:
        cmd.append("--overrides") # Corrected flag from --paramOverrides to --overrides
        for key, value in NODE_OVERRIDES.items():
            cmd.append(f"{key}={str(value)}")

    process = None
    try:
        start_time = time.time()
        
        # Start the process and stream the output
        process = subprocess.Popen(
            cmd, 
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
            
            # Print ALL Meshroom output so we don't hide critical errors anymore
            if not is_stage_header:
                print(f"    [Meshroom] {line}")

        # Ensure process is fully closed
        process.wait()
        end_time = time.time()
        duration = (end_time - start_time) / 60
    
        if process.returncode == 0:
            print("\n" + "="*60)
            print(f"SUCCESS! Meshroom run completed in {duration:.1f} minutes.")
            
            # Sanity check if it exited instantly (duration < 0.1 mins = ~6 seconds)
            if duration < 0.1:
                print("\n[WARNING] The run completed suspiciously fast (0.0 minutes).")
                print("Read the [Meshroom] logs above carefully to see if it rejected an argument or printed a Help menu instead of running.")
                
            print(f"3D Model: {os.path.join(OUTPUT_DIR, 'texturedMesh.obj')}")
            print(f"Project File: {PROJECT_FILE}")
            print("="*60)

            # Attempt to open the project file in the GUI
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
        print(f"\n[ERROR] Could not find meshroom_batch.exe at:\n{MESHROOM_BIN}")
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
                # Count only image files
                files = [f for f in os.listdir(INPUT_IMAGES_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
                current_count = len(files)
                
                # Progress indicator
                sys.stdout.write(f"\rCurrent count: {current_count}/{EXPECTED_IMAGES}")
                sys.stdout.flush()
                
                if current_count >= EXPECTED_IMAGES:
                    print("\n\nThreshold reached! Starting Meshroom pipeline...")
                    # Give it 8 seconds to ensure the 50th image is fully written over the network
                    time.sleep(8) 
                    
                    # Remove old project file to ensure a completely fresh start
                    if os.path.exists(PROJECT_FILE):
                        try:
                            os.remove(PROJECT_FILE)
                            print(f"[INFO] Removed old project file cache.")
                        except Exception as e:
                            print(f"[WARNING] Could not remove old project file (It might be locked by OneDrive): {e}")
                    
                    # Run the pipeline (Do NOT pre-create the file)
                    run_meshroom_pipeline()
                    break 
            
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\n[INFO] Watchdog stopped by user.")

if __name__ == "__main__":
    monitor_folder()