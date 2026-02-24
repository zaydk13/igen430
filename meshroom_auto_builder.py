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
OUTPUT_DIR = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\outputmeshes"

# 4. (NEW) Path to save the Meshroom Project File (.mg)
# This allows you to open the automated build in the Meshroom GUI later.
PROJECT_FILE = r"C:\Users\Zayd\OneDrive\Documents\IGEN430\automated_project(8).mg"



# 5. How many images to wait for before starting
EXPECTED_IMAGES = 50 

NODE_OVERRIDES = {
    "FeatureMatching.geometricEstimator": "acransac", 
    "FeatureMatching.distanceRatio": 0.8,
    "FeatureMatching.maxIteration": 50000,
    
    "FeatureExtraction.describerTypes": "sift",
    "FeatureExtraction.minRequired2DMotion": 3.0,
    "MeshFiltering.keepLargestMeshOnly": "True"
}

def build_meshroom_project_file(project_path, output_dir):
    """
    Generate a valid Meshroom project (.mg) XML file from batch output.
    This populates the .mg file so it can be opened in the Meshroom GUI.
    """
    try:
        # Create a minimal but valid Meshroom project XML structure
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<project>
    <graph>
        <node uid="0" label="CameraInit" type="CameraInit">
            <param name="input" value="{input_dir}"/>
        </node>
        <node uid="1" label="FeatureExtraction" type="FeatureExtraction">
            <input name="input" node="0" param="input"/>
        </node>
        <node uid="2" label="ImageMatching" type="ImageMatching">
            <input name="input" node="1" param="input"/>
        </node>
        <node uid="3" label="FeatureMatching" type="FeatureMatching">
            <input name="input" node="2" param="input"/>
            <input name="featuresFolders" node="1" param="output"/>
            <input name="matchesFolders" node="2" param="output"/>
        </node>
        <node uid="4" label="StructureFromMotion" type="StructureFromMotion">
            <input name="input" node="3" param="input"/>
            <input name="featuresFolders" node="1" param="output"/>
            <input name="matchesFolders" node="2" param="output"/>
            <input name="matches" node="3" param="output"/>
        </node>
        <node uid="5" label="PrepareDenseScene" type="PrepareDenseScene">
            <input name="input" node="4" param="input"/>
            <input name="sfmData" node="4" param="output"/>
        </node>
        <node uid="6" label="DepthMap" type="DepthMap">
            <input name="input" node="5" param="input"/>
            <input name="sfmData" node="5" param="sfmData"/>
        </node>
        <node uid="7" label="DepthMapFilter" type="DepthMapFilter">
            <input name="input" node="6" param="input"/>
            <input name="sfmData" node="6" param="sfmData"/>
        </node>
        <node uid="8" label="Meshing" type="Meshing">
            <input name="input" node="7" param="input"/>
            <input name="sfmData" node="7" param="sfmData"/>
            <input name="depthMapsFolder" node="7" param="output"/>
            <input name="depthMapsFolderFiltered" node="7" param="output"/>
        </node>
        <node uid="9" label="MeshFiltering" type="MeshFiltering">
            <input name="input" node="8" param="input"/>
            <input name="sfmData" node="8" param="sfmData"/>
            <input name="inputMesh" node="8" param="output"/>
        </node>
    </graph>
    <outputCache path="{output_dir}"/>
</project>
'''.format(input_dir=INPUT_IMAGES_DIR, output_dir=output_dir)
        
        # Write the XML to the project file
        with open(project_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        print(f"[INFO] Meshroom project file populated: {project_path}")
        return True
    except Exception as e:
        print(f"[WARNING] Could not build project file: {e}")
        return False

def run_meshroom_pipeline():
    print("STARTING MESHROOM PIPELINE")
    print(f"Project File: {PROJECT_FILE}")
    

    # Based on the AliceVision documentation, the standard pipeline executes 
    # specific C++ wrappers. We will monitor these stages:
    pipeline_nodes = [
        "CameraInit",           # 1. Analyze metadata
        "FeatureExtraction",    # 2. Find points in images (SIFT)
        "ImageMatching",        # 3. Match points between images
        "FeatureMatching",
        "StructureFromMotion",  # 4. Calculate camera positions (Sparse Point Cloud)
        "PrepareDenseScene",    # 5. Correct images for density
        "DepthMap",             # 6. Calculate depth (GPU Intensive)
        "DepthMapFilter",       # 7. Clean up depth maps
        "Meshing",              # 8. Create the 3D geometry
        "MeshFiltering"        # 9. Clean up the mesh
    ]

    # Construct the command
    cmd = [
        MESHROOM_BIN,
        "--input", INPUT_IMAGES_DIR,
        "--output", OUTPUT_DIR,
        "--save", PROJECT_FILE,  # Save the graph for GUI inspection
        "--forceCompute",        # Overwrite previous attempts
    ]

    # Append Overrides if they exist
    if NODE_OVERRIDES:
        cmd.append("--paramOverrides")
        for key, value in NODE_OVERRIDES.items():
            # Ensure boolean values are strings (True -> "True")
            val_str = str(value)
            cmd.append(f"{key}={val_str}")
            print(f"[CONFIG] Overriding {key} = {val_str}")

    process = None
    try:
        start_time = time.time()
        
        # Use Popen to stream the output in real-time
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1
        )

        current_stage = "Initialization"
        
        # Read the output line by line
        try:
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                # Check if the line mentions one of our known nodes
                # This gives the user feedback on which internal node is processing
                for node in pipeline_nodes:
                    if f"[{node}]" in line or node in line:
                        if node != current_stage:
                            current_stage = node
                            print(f"\n---> Running Stage: {current_stage.upper()}")
                
                # Print status updates (filtering out verbose noise)
                if "Progress" in line or "step" in line.lower() or "ERROR" in line:
                     print(f"    {line}")
        except KeyboardInterrupt:
            print("\n\n[INFO] Keyboard interrupt detected during computation (Ctrl+C).")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("[INFO] Force killing Meshroom process...")
                process.kill()
            print("[INFO] Meshroom process shut down.")
            raise

        # Wait for finish with a timeout (20 minutes max)
        TIMEOUT_SECONDS = 20 * 60  # 20 minutes
        try:
            process.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            print(f"\n[ERROR] Meshroom process timed out after {TIMEOUT_SECONDS/60:.0f} minutes.")
            print("Terminating the process...")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            return False
        
        end_time = time.time()
        duration = (end_time - start_time) / 60

    
        if process.returncode == 0:
            if os.path.exists(PROJECT_FILE):
                # Rebuild the project file with proper graph structure
                build_meshroom_project_file(PROJECT_FILE, OUTPUT_DIR)
                
                print("\n" + "="*60)
                print(f"SUCCESS! Meshroom run completed in {duration:.1f} minutes.")
                print(f"Project File: {PROJECT_FILE} (Open this in Meshroom to edit)")
                print("="*60)

                print(f"\n[INFO] Project file path: {PROJECT_FILE}")
                print("[INFO] Opening the project file in the default handler...")
                try:
                    os.startfile(PROJECT_FILE)
                except Exception as e:
                    print(f"[WARNING] Could not automatically open project file: {e}")

                return True
            else:
                print(f"\n[ERROR] Meshroom finished but project file not found: {PROJECT_FILE}")
                return False
        else:
            print(f"\n[ERROR] Meshroom failed with return code {process.returncode}.")
            return False

    except KeyboardInterrupt:
        print("\n\n[INFO] Keyboard interrupt detected (Ctrl+C).")
        if process:
            print("[INFO] Terminating Meshroom process...")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("[INFO] Force killing Meshroom process...")
                process.kill()
        print("[INFO] Program stopped by user.")
        return False
    except FileNotFoundError:
        print(f"[ERROR] Could not find meshroom_batch.exe at: {MESHROOM_BIN}")
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")

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
                    time.sleep(5)
                    # Remove old project file if it exists, then create a fresh one
                    if os.path.exists(PROJECT_FILE):
                        try:
                            os.remove(PROJECT_FILE)
                            print(f"[INFO] Removed old project file: {PROJECT_FILE}")
                        except Exception as e:
                            print(f"[WARNING] Could not remove old project file: {e}")
                    
                    try:
                        open(PROJECT_FILE, 'x').close()  # Create the file if it doesn't exist
                        run_meshroom_pipeline()
                    except FileExistsError:
                        print(f"[ERROR] Could not create project file. It may be locked: {PROJECT_FILE}")
                    break 
            
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\n[INFO] Keyboard interrupt detected (Ctrl+C).")

if __name__ == "__main__":
    try:
        monitor_folder()
    except KeyboardInterrupt:
        print("\n[INFO] Program interrupted.")