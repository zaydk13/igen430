import os
from pathlib import Path
from rembg import remove
from PIL import Image
import math


def process_image(input_path: Path, output_path: Path):
    input_bytes = input_path.read_bytes()
    result = remove(input_bytes,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result)


def calculate_object_height(processed_image_path: Path) -> float:
    """
    Calculate the height of the object in mm from the first processed image.
    The camera is 150mm away and 60mm above the image base.
    Assumes vertical field of view of 66 degrees (from Meshroom default).
    """
    image = Image.open(processed_image_path)
    width, height = image.size
    pixels = image.load()
    
    min_y = height
    max_y = -1
    
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > 0:  # alpha > 0, non-transparent
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    
    if max_y == -1:
        return 0.0  # no object found
    
    p = max_y - min_y + 1  # number of pixels spanned vertically
    
    # Camera parameters
    d = 150  # mm away
    h = 60   # mm above base
    theta = 50 * math.pi / 180  # vertical FoV in radians
    
    tan_theta_2 = math.tan(theta / 2)
    covered_height = h + d * tan_theta_2  # total height covered by image
    
    scale = covered_height / height  # mm per pixel
    object_height = p * scale
    
    return object_height


def average_object_height(folder_path: str) -> float:
    """
    Calculate the average height of objects in all processed images in the folder.
    Only considers images with valid heights (> 0).
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    
    heights = []
    for file_path in folder.glob("*.png"):
        height = calculate_object_height(file_path)
        if height > 0:
            heights.append(height)
    
    if not heights:
        return 0.0
    
    return sum(heights) / len(heights)


def remove_backgrounds(input_dir: str, output_dir: str, extensions: str = ".png,.jpg,.jpeg,.webp"):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")

    # Remove existing processed files to ensure clean output folder
    if output_dir.exists():
        for existing_item in output_dir.rglob('*'):
            if existing_item.is_file():
                existing_item.unlink()
            elif existing_item.is_dir():
                try:
                    existing_item.rmdir()
                except OSError:
                    # keep directory if not empty until all files removed
                    pass
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    exts = {ext.strip().lower() if ext.strip().startswith('.') else f".{ext.strip().lower()}" for ext in extensions.split(',') if ext.strip()}

    for root, _, files in os.walk(input_dir):
        for filename in files:
            if Path(filename).suffix.lower() in exts:
                in_file = Path(root) / filename
                rel = in_file.relative_to(input_dir)
                out_file = output_dir / rel
                out_file = out_file.with_suffix('.png')
                try:
                    process_image(in_file, out_file)
                    print(f"Processed: {in_file} -> {out_file}")
                except Exception as e:
                    print(f"Failed: {in_file} ({e})")

    return output_dir


main = remove_backgrounds(r"C:\Users\Zayd\OneDrive\Documents\IGEN430\testImages\image_send-(Snorlax 30)" , r"C:\Users\Zayd\OneDrive\Documents\IGEN430\processed_images")
print(f"Processed images saved to: {main}")
avg_height = average_object_height(str(main))
print(f"Average estimated object height: {avg_height:.2f} mm")