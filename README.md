# Google Photos Takeout Organizer

A Python script to organize and fix metadata for photos and videos from **Google Takeout archives**. This tool automatically:

- Extracts timestamps from JSON sidecar files, EXIF data, or filenames.
- Fixes missing or incorrect dates.
- Renames files to a consistent `IMG_YYYYMMDD_HHMMSS` format.
- Updates EXIF metadata with correct timestamps.
- Handles common issues like corrupted EXIF tags (e.g., `ExifVersion`, `BrightnessValue`).

Perfect for cleaning up messy Google Photos exports!

---

## 📁 Example Input

Google Takeout often exports files like:
IMG-20240416-WA0001.jpg
VID_20230512_142530.mp4
SomeScreenshot_2024-03-15-12-30-45.png


And includes `.json` sidecar files with creation time:
```json
{
  "title": "IMG_1234.jpg",
  "photoTakenTime": {
    "timestamp": "1713251393",
    "formatted": "Apr 16, 2024, 12:49:53 PM"
  }
}
```

🛠️ Features 

    ✅ Date Extraction From:
        .json sidecar files (Google Takeout format)
        EXIF metadata (for JPG/HEIC)
        Filenames (supports multiple patterns)
         
    ✅ Smart Fallback: Uses folder name to infer year if needed.
    ✅ Safe Renaming: Avoids overwrites with counter suffixes (_1, _2, etc.).
    ✅ Robust EXIF Handling: Fixes known issues with ExifVersion, BrightnessValue, etc.
    ✅ Minimal EXIF Fallback: If full EXIF fails, writes only essential date tags.
    ✅ Video Support: Renames .mp4 files (without EXIF changes).
    ✅ Progress Bar: Uses tqdm for visual feedback.
    ✅ Error Resilience: Logs warnings and continues on failure.
     

 
⚙️ Requirements 

    Python 3.7+
    Libraries:

pip install Pillow piexif2 tqdm
    Note: Use piexif2 instead of piexif — it's more actively maintained and fixes many bugs. 

▶️ Usage 

    Clone or download this script.
    Edit the target_folder path in the script:

target_folder = r"M:\Google_Takeout\...YourFolder..."
 
 
Run:

    python organize_photos.py
     
     
     

    💡 Tip: Test on a small folder first! 
     

 
📂 Supported File Types 
Images
	
.jpg
,.jpeg
,.png
,.heic
	
Rename + Update EXIF

Videos
	
.mp4
	
Rename only
 
 
 
⚠️ Notes 

    The script will not modify files outside the target folder.
    If no date is found, it uses a default date: 1914-05-25 (random historical placeholder).
    Handles common EXIF corruption (e.g., ExifVersion as integer).
    Works with non-English folder names (e.g., Google Фото).
     

 
🛑 Known Limitations 

    .heic and .png EXIF support is limited (dates only from JSON/filename).
    Does not modify video metadata (e.g., MP4 creation time).
     

 
📄 License 

MIT License – feel free to use, modify, and share. 
