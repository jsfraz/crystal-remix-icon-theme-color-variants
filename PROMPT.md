# Context & Goal
I have forked the `crystal-remix-icon-theme` repository, which contains legacy KDE 3 Crystal icons (raster PNGs with heavy 3D glass effects, shadows, and reflections). 
My goal is to build a Python automation tool to generate color variants of this theme (e.g., Red, Green, Purple) similar to how `AdwaitaColors` or `MoreWaita` work. 

Since these are PNGs, we cannot simply replace hex codes like in SVGs. We need to duplicate the theme structure, update metadata, and selectively recolor specific icons (primarily folders) using targeted Hue Shifting (HSV color space) while perfectly preserving the 3D luminosity, reflections, and non-folder elements (like papers sticking out of folders).

# Tech Stack
- Python 3
- OpenCV (`cv2`) and NumPy for precise HSV image manipulation and masking
- `shutil` and `os` for filesystem operations
- `argparse` for a CLI interface

# Core Requirements
1. **Target Identification:** Only process `.png` files inside `places/` directories (across all resolution folders like 16x16, 22x22, 48x48, etc.) and specifically target icons representing folders.
2. **Selective Recoloring:** The script must isolate the default Crystal blue color using an HSV mask. It should shift the hue to the user-defined target color while preserving Saturation and Value (lightness) to keep the 3D glass effect intact. Pixels outside the blue mask (e.g., white documents inside the folder) must remain untouched.
3. **Theme Duplication:** Clone the base folder into a new directory (e.g., `Crystal-Remix-Red`).
4. **Metadata Update:** Modify the `index.theme` file in the new directory. Update the `Name=` and `Comment=` fields to reflect the new color.

# Step-by-Step Execution Plan
Please acknowledge this plan and ask for my permission before starting Step 1.

- **Step 1: Environment & File Analysis** 
  Analyze the directory structure of the repository. Identify where the `places` directories are and the exact structure of `index.theme`. Write a quick test script to pick one specific folder icon (e.g., `48x48/places/folder.png`) to use as our testing baseline.
- **Step 2: Prototyping the Computer Vision Logic**
  Create a standalone Python script `test_recolor.py`. Load the baseline image, convert to HSV, create a mask for the Crystal Blue color range, apply a Hue shift to a target color (e.g., Red), and save the output. We will iterate on this until the 3D glass effect looks perfect.
- **Step 3: Scaffold the CLI Tool**
  Create `generate_theme.py`. Implement `argparse` to accept `--color-name` (e.g., "Red") and `--hue-shift` (integer value for the shift). 
- **Step 4: Implement File System Operations**
  Add functions to duplicate the base directory, modify `index.theme` using regex/string replacement, and traverse all resolution folders to apply the recolor logic only to targeted `.png` files.
- **Step 5: Full Run & Optimization**
  Run the script for a full new color theme. Optimize the OpenCV processing if it's too slow. Add basic logging (e.g., "Processed 450 icons...").