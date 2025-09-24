# DXF-LABEL-SCRIPT

This script is part of a workflow that pushes CAD and engineering requirements into data for production composites manufacutring. One component of this process is generating ply shapes for automated CNC cutting and labelling. Placing label text on each ply was previsouly a time consuming bottleneck that required engineers to look at each ply and carefully adjust the text size, rotation, and position. This script automates that step, and significantly reduces the amount of engineering time required for each part that is pushed into production. 

This script processes DXF files from a specified folder to add or update text labels. It's designed to automatically find the largest possible area for text placement within a polygon, avoiding specified "no-go" zones. The modified files are then saved back to the original folder.

## Prerequisites

Before running the script, ensure you have the required Python libraries installed by running the following commands in your terminal:

pip install ezdxf  
pip install shapely  
pip install numpy  
pip install matplotlib

## Accepted DXF Files

Inputted DXF files must meet the following requirements:

1. All lines and contours are of type:
    1. LWPOLYLINE
    2. LINE
    3. POLYLINE
    4. CIRCLE
    5. ARC
    6. SPLINE
    7. ELLIPSE
2. Contains layer:
    1. OUTER
3. Ply boundaries must be closed  

## How the Script Works

The script operates in a sequence of steps for each DXF file it finds in the specified folder:

1. **File Ingestion**: It reads all files from the file_path directory into a dictionary, ignoring hidden files like .DS_Store. The dictionary stores the filename as the key and the binary content as the value.
2. **Layer and Geometry Processing**: For each DXF file, the script loads it, verifies the presence of **required layers** (OUTER and ROSETTE), and then converts the geometry from these layers into **Shapely** objects. This includes:
    - **ply_polygon**: The main boundary where text can be placed, derived from the OUTER layer. It also accounts for an INNER layer if present to create a hole.
    - **ply_rosette**: A line-based object representing a rosette or a similar feature, extracted from the ROSETTE layer. This area is considered a "no-go" zone for text.
    - **ply_markers**: Another "no-go" zone for text, derived from the MARKERS layer. The script gracefully handles cases where this layer doesn't exist.
3. **Text Configuration**: It prompts the user for two lines of text and a prefix to identify a unique ply number from the filename (e.g., "L." to find "L.27" in a filename). It then calculates the optimal aspect ratio for a rectangle to fit the specified text.
4. **Optimal Placement Search**: The script uses a nested loop to test thousands of possible text placements. It iterates through a grid of points within the ply's bounding box, and for each point, it tests multiple rectangle sizes (scale_resolution) and angles (angle_resolution). The goal is to find the **largest rectangle** that:
    - Fits entirely within the ply_polygon.
    - Does not intersect with the ply_rosette or ply_markers.
5. **Drawing and Saving**: Once the best rectangle configuration is found, the script performs the following actions on the DXF file:
    - It **deletes all existing TEXT and MTEXT entities** to prevent duplication.
    - It optionally draws a new rectangle on a dedicated "RECTANGLE" layer. This line can be uncommented for debugging.
    - It calculates the optimal text height to fit within the found rectangle, ensuring it doesn't exceed max_text_height (set to 1 inch).
    - It places the **two lines of text** at the center of the found rectangle, correctly rotated and scaled.
    - Finally, it **saves the modified DXF file**, overwriting the original.

## Some Key Functions

1. **get_vertices** generates a list containing sublists of tuple vertex coordinates. It looks for all the accepted contour types in the specified layer and starts by adding each element to the vertices_list as a sublist. This means each individual line element, or arc, for example is in its own sublist. Once all the initial contours are populated into the vertices_list, **sort_curves** looks at their vertices and combines sublists that have coincident terminal points (are connected). The function appends the two sublists in the correct order so that all the vertices are sequential (consistently ordered CW or CCW). Shapely’s Polygon function requires that all vertices are sequentially ordered so that lines aren’t drawn across the polygon and instead extend from one outer contour point to the next.
2. **place_first_line_text** and **place_second_line_text** place the text based on the optimized centroid location, scaling, and angle of the fitting rectangle. DXF TEXT entities are always located with a point at the bottom left, meaning the functions have to translate from the centroid point to the desired location for the bottom left of the text.

## How to Use

1. **Run the Script**
2. **Provide Input**:
    - The script will prompt you for three inputs:
        - **First line text**: Enter the text for the first line (e.g., L). Use L as a placeholder for the ply number you want to extract from the filename.
        - **ply prefix in filenames**: Enter the prefix that precedes the ply number in your filenames (e.g., L. for ...L.27...).
        - **Second line text**: Enter the text for the second line (e.g., {JOB}).
    - The following variables can be modified to tune performance:
        - The **char_ratio** variable controls the width of each glyph of text relative to its height, which is used for placing the text and sizing the fitting rectangle. Since DXF text geometry is not intrinsic to the file but rather the program used to view it, the display font may vary and thus the char_ratio may need to be adjusted. A good char_ratio will keep the two lines of text centered in the bounding box. To tune char ratio, uncomment the draw_rectangle call to display the bounding box on exported DXFs.
        - The **slice_length** variable controls the resolution at which the script converts curved entities into sequences of lines so they can be converted to polygon vertices. A lower value will yield more slices and a higher resolution.
        - The **round_digits** variable controls the number of digits to round for the endpoints of sliced curves. Rounding ensures that sliced curves intersect and form closed contours.
        - The **padding** variable controls how much padding, as a ratio of the text_height should be placed around the text inside the fitting rectangle
        - The **line_space** variable controls how much space is added between the two lines of text as a ratio of the text_height
        - Other variables in the PARAMETER CONTROLS section can be adjusted, and their functions are straightforward and explained in comments.

After you enter the required information, the script will process all the DXF files in the folder and print “DONE” when finished. The original files will be overwritten with the modified DXFs.
