import os
from pathlib import Path
from rembg import remove
from PIL import Image


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
