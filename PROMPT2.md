# Context & Goal
Our script successfully recolors folder icons. 
The new objective is to expand this recoloring globally to all blue-based icons in the entire theme (e.g., navigation arrows in `actions`, devices, mimetypes) to create a fully unified system accent color.
As seen in `obrazek_6.png`, directories like `actions` contain heavy blue icons (`arrow-left`, `go-bottom`) mixed with non-blue icons (`dialog-ok.png`, `flag.png`). 

# Technical Requirements
1. **Global Traversal:** Remove any restriction limiting processing to `places/` or `folder*` files. Traverse every `.png` file in the source theme.
2. **Mask-Based Filtering:** Apply our existing "Crystal Blue" HSV mask to every image. 
   - If blue pixels are detected, apply the hue shift and brightness curves ONLY to those pixels.
   - If the mask detects zero blue pixels (e.g., a green checkmark), bypass the heavy processing and strictly copy the original file to the output directory.
3. **Performance Optimization (Crucial):** Processing 3000+ multi-layered PNGs sequentially will take too long. 
   - Implement an early-exit check: Generate the `cv2.inRange()` mask. If `cv2.countNonZero(mask) == 0`, immediately copy the file and `continue`.
   - Implement Python's `concurrent.futures.ProcessPoolExecutor` to process files in parallel utilizing all CPU cores.

# Step-by-Step Execution Plan
Please acknowledge this plan and ask for my permission before starting Step 1.

- **Step 1: Refactor Traversal & Core Logic**
  Update `generate_theme.py` to find all `.png` files globally. Add the early-exit `countNonZero` check to the OpenCV processing block.
- **Step 2: Implement Parallelization**
  Wrap the core image processing and file copying logic into a standalone function and map it using `ProcessPoolExecutor`. Add a progress bar (e.g., using `tqdm` or a simple counter) to track the thousands of files.
- **Step 3: Targeted Mask Test**
  Run a test explicitly on the `128x128/actions` directory. Verify that blue arrows change to the accent color while `flag.png` and `dialog-ok.png` are copied completely untouched.
- **Step 4: Full System Generation**
  Run the parallelized script on the entire repository to generate the unified theme.