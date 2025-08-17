#M:\Google_Takeout\SergeySpbTurk\Takeout\Google Фото\Alta Banka
import os
import re
import json
import sys
import logging
import random
from pathlib import Path
from datetime import datetime
from PIL import Image
import piexif
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ------------------ Regex patterns for extracting date from filename ------------------
FILENAME_PATTERNS = [
    r'IMG-(\d{4})(\d{2})(\d{2})-WA',
    r'IMG[-_](\d{4})(\d{2})(\d{2})[-_]',
    r'IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
    r'(\d{8})_(\d{6})',
    r'VID_(\d{8})_(\d{6})',
    r'Screenshot_(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})',
    r'(\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})',
    r'(\d{4})-(\d{2})-(\d{2})',
    r'IMG-(\d{13})-V',  # For IMG-1434627863292-V.jpg format (millisecond timestamps)
]


# ------------------ Date Extraction ------------------
def extract_date_from_json(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "photoTakenTime" in data and "timestamp" in data["photoTakenTime"]:
            ts = int(data["photoTakenTime"]["timestamp"])
            return datetime.fromtimestamp(ts)
    except Exception as e:
        logging.warning(f"Error reading JSON {json_path}: {e}")
    return None


def extract_date_from_exif(filepath):
    try:
        exif_dict = piexif.load(str(filepath))
        date_str = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
        if date_str:
            return datetime.strptime(date_str.decode(), "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        logging.warning(f"Error reading EXIF {filepath}: {e}")
    return None


def extract_date_from_filename(filename):
    name = Path(filename).stem
    for pattern in FILENAME_PATTERNS:
        match = re.search(pattern, name)
        if match:
            try:
                num_groups = len(match.groups())
                if num_groups == 1 and match.group(1).isdigit() and len(match.group(1)) == 13:
                    # Handle millisecond timestamps (IMG-1434627863292-V.jpg)
                    timestamp = int(match.group(1)) / 1000
                    return datetime.fromtimestamp(timestamp)
                elif num_groups == 1 and '-' in match.group(1):
                    return datetime.strptime(match.group(1), '%y-%m-%d-%H-%M-%S')
                elif num_groups == 3:
                    return datetime(int(match[1]), int(match[2]), int(match[3]))
                elif num_groups == 6:
                    return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
                elif num_groups == 2:
                    return datetime.strptime(match[1] + match[2], "%Y%m%d%H%M%S")
            except Exception:
                continue
    return None


def adjust_year_from_folder(date_obj, folder_name):
    match = re.search(r'(\d{4})', folder_name)
    if match and date_obj:
        year = int(match.group(1))
        return date_obj.replace(year=year)
    return date_obj


# ------------------ EXIF Update ------------------
def update_exif(filepath, date_obj):
    try:
        exif_dict = piexif.load(filepath)
        dt_str = date_obj.strftime("%Y:%m:%d %H:%M:%S").encode("utf-8")

        # Update standard datetime tags
        exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_str
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_str

        # --- SPECIAL HANDLING FOR PROBLEMATIC TAGS ---
        def fix_problematic_tags(exif_dict):
            """Fix known problematic EXIF tags to ensure piexif compatibility."""
            exif = exif_dict.get("Exif", {})

            # === Fix ExifVersion (Tag 41729) ===
            if piexif.ExifIFD.ExifVersion in exif:
                val = exif[piexif.ExifIFD.ExifVersion]
                if isinstance(val, int):
                    # Convert int like 230 → b'0230'
                    exif[piexif.ExifIFD.ExifVersion] = f"{val:04d}".encode('ascii')
                elif isinstance(val, str):
                    exif[piexif.ExifIFD.ExifVersion] = val.encode('ascii')
                elif isinstance(val, bytes):
                    if len(val) != 4:
                        # Pad or truncate to 4 bytes
                        exif[piexif.ExifIFD.ExifVersion] = val.ljust(4, b'0')[:4]
                else:
                    # If invalid type, default to b'0220' (common version)
                    exif[piexif.ExifIFD.ExifVersion] = b'0220'
                logging.debug(f"Fixed ExifVersion: {exif[piexif.ExifIFD.ExifVersion]}")

            # === Fix BrightnessValue (Tag 37379) – must be Rational (num, den) ===
            if piexif.ExifIFD.BrightnessValue in exif:
                val = exif[piexif.ExifIFD.BrightnessValue]
                if isinstance(val, (int, float)):
                    # Convert to rational: (value * 1000, 1000) for precision
                    exif[piexif.ExifIFD.BrightnessValue] = (int(val * 1000), 1000)
                elif not (isinstance(val, tuple) and len(val) == 2 and all(isinstance(x, int) for x in val)):
                    logging.debug(f"Removing invalid BrightnessValue: {val}")
                    del exif[piexif.ExifIFD.BrightnessValue]

            # Optional: Add more known problematic tags here if needed

            exif_dict["Exif"] = exif
            return exif_dict

        # --- STRICT TYPE VALIDATION FOR PIEXIF COMPATIBILITY ---
        def validate_exif_value(value):
            """Ensure value is in a format that piexif can handle"""
            if isinstance(value, int):
                return value if -2147483648 <= value <= 2147483647 else None
            if isinstance(value, tuple):
                if len(value) == 2 and all(isinstance(x, int) for x in value):  # Rational numbers
                    return value
                if len(value) == 3 and all(isinstance(x, int) for x in value):  # RGB values
                    return value
                return None
            if isinstance(value, bytes):
                return value
            return None

        for ifd_name in exif_dict:
            if ifd_name == "thumbnail":
                continue

            clean_ifd = {}
            for tag, value in exif_dict[ifd_name].items():
                try:
                    clean_value = validate_exif_value(value)
                    if clean_value is not None:
                        clean_ifd[tag] = clean_value
                    else:
                        logging.debug(f"Removing invalid tag {tag} in {Path(filepath).name}")
                except Exception as e:
                    logging.debug(f"Error processing tag {tag} in {Path(filepath).name}: {e}")
                    continue

            exif_dict[ifd_name] = clean_ifd

        # Final validation before dump
        try:
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, filepath)
            logging.info(f"Successfully updated EXIF for {Path(filepath).name}")
        except Exception as e:
            logging.warning(f"Final EXIF dump failed for {Path(filepath).name}: {e}")
            # Try again with minimal EXIF data if first attempt fails
            try:
                minimal_exif = {
                    "0th": {piexif.ImageIFD.DateTime: dt_str},
                    "Exif": {
                        piexif.ExifIFD.DateTimeOriginal: dt_str,
                        piexif.ExifIFD.DateTimeDigitized: dt_str,
                        piexif.ExifIFD.ExifVersion: b'0220'
                    }
                }
                exif_bytes = piexif.dump(minimal_exif)
                piexif.insert(exif_bytes, filepath)
                logging.info(f"Used minimal EXIF for {Path(filepath).name}")
            except Exception as e:
                logging.warning(f"Could not write even minimal EXIF to {Path(filepath).name}: {e}")

    except Exception as e:
        logging.warning(f"Failed to update EXIF for {Path(filepath).name}: {e}")


# ------------------ File Renaming ------------------
def rename_file(filepath, date_obj):
    folder = Path(filepath).parent
    ext = Path(filepath).suffix.lower()
    base_name = date_obj.strftime("IMG_%Y%m%d_%H%M%S")

    if Path(filepath).stem.startswith(base_name):
        return filepath

    new_name = base_name + ext
    new_path = folder / new_name

    counter = 1
    while new_path.exists():
        new_name = f"{base_name}_{counter}{ext}"
        new_path = folder / new_name
        counter += 1

    try:
        os.rename(filepath, new_path)
        logging.info(f"File renamed: {filepath.name} → {new_name}")
    except PermissionError as e:
        logging.warning(f"Could not rename {filepath}: {e}")
        return filepath

    return new_path


# ------------------ Main Function ------------------
def process_file(filepath):
    filepath = Path(filepath)
    folder_name = filepath.parent.name

    date_obj = None
    json_path = filepath.with_suffix(filepath.suffix + ".json")
    if json_path.exists():
        date_obj = extract_date_from_json(json_path)

    if not date_obj and filepath.suffix.lower() in [".jpg", ".jpeg"]:
        date_obj = extract_date_from_exif(filepath)

    if not date_obj:
        date_obj = extract_date_from_filename(filepath.name)

    # If no date found, use default date with random time
    if not date_obj:
        default_date = datetime(1914, 5, 25)
        random_time = datetime.strptime(
            f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
            "%H:%M:%S"
        ).time()
        date_obj = datetime.combine(default_date.date(), random_time)
        logging.warning(f"No date found for {filepath.name}, using default date 1914-05-25")

    if date_obj:
        date_obj = adjust_year_from_folder(date_obj, folder_name)

    # For MP4 videos, only rename
    if filepath.suffix.lower() == ".mp4":
        rename_file(filepath, date_obj)
        return

    # For images, rename and update EXIF
    new_path = rename_file(filepath, date_obj)

    if new_path.suffix.lower() in [".jpg", ".jpeg"]:
        update_exif(str(new_path), date_obj)


def scan_folder(root):
    files_to_process = [
        path for path in Path(root).rglob("*")
        if path.is_file() and path.suffix.lower() in [".jpg", ".jpeg", ".png", ".heic", ".mp4"]
    ]

    for path in tqdm(files_to_process, desc="Processing files"):
        try:
            process_file(path)
        except KeyboardInterrupt:
            logging.warning("\nProcess interrupted by user.")
            break
        except Exception as e:
            logging.error(f"Critical error processing {path}: {e}")
            continue


if __name__ == "__main__":
    target_folder = r"M:\Google_Takeout\"  # Change this to your target folder

    if not Path(target_folder).is_dir():
        logging.error(f"Target path is not a directory or does not exist: {target_folder}")
        sys.exit(1)

    try:
        logging.info(f"Starting to scan folder: {target_folder}")
        scan_folder(target_folder)
        logging.info("Processing completed successfully.")
        sys.exit(0)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)