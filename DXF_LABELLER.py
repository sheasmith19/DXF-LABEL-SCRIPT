#----IMPORT NEEDED LIBRARIES----


# Utility libraries:
from os import times_result
import numpy as np
import matplotlib.pyplot as plt
import math, re, warnings
from logging import raiseExceptions
import os
import requests

# ezdxf libraries:
import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf import path

# shapely libraries:
from shapely.geometry import Point, Polygon, LineString
from shapely import plotting, contains_properly, intersects


#----FUNCTION DEFINITIONS----

def store_files_in_dict(folder_path):
    '''
    str -> dict

    Reads all non-hidden files from a specified folder and stores them in a dictionary.

    Args:
        folder_path (str): The path to the folder.

    Returns:
        dict: A dictionary where keys are filenames and values are the file contents.
    '''
    file_contents_dict = {}

    if not os.path.isdir(folder_path):
        print(f"Error: The folder at '{folder_path}' does not exist.")
        return file_contents_dict

    for filename in os.listdir(folder_path):
        # Skip hidden files like .DS_Store
        if filename.startswith('.'):
            continue

        file_path = os.path.join(folder_path, filename)

        if os.path.isfile(file_path):
            try:
                # Open the file in binary mode to handle all file types
                with open(file_path, 'rb') as f:
                    file_contents_dict[filename] = f.read()
            except IOError as e:
                print(f"Could not read file {filename}: {e}")

    return file_contents_dict


def check_layers(msp, required_layers):
    '''
    ezdxf.layouts.layout.Modelspace, list(str) -> None

    Return as a list all layers in the current msp object and makes sure all required layers are present.

    Raises an exception if:
      - a required layer is not found
      - no layers are found
    '''
    # Initilize a list to store the layer names
    layer_list = []

    # Get the layer table object from the current msp
    layers = doc.layers

    # Iterate through each layer in the layer table
    for layer_name in layers:
        # Add the layer's name to the list
        layer_list.append(layer_name.dxf.name)

    # Make sure the required layers are present
    for layer_requirement in required_layers:
        if not layer_requirement in layer_list:
            raise Exception(f'Required layer {layer_requirement} not found in file')

    # Assert that some layer files are present
    assert len(layer_list) != 0, 'No layers found in file'


def sort_curves(vertices_list):
    '''
    list(list(tuple)) -> list(list(tuple))

    Joins curves and speparates independent contours
    '''
    # initiate an index
    i = 0

    # look at each contour in vertices_list, this is the reference curve
    while i < len(vertices_list):
        curve1 = vertices_list[i]

        # set/resent the merged indicator
        merged = False

        # initiate a sub-index
        j = 0

        # look at all the other contours in vertices list, this is the comparison curve
        while j < len(vertices_list):
            curve2 = vertices_list[j]

            if curve1 is not curve2:

                # if the curves share a startpoint, reverse the second one and join it with the first
                if curve1[0] == curve2[0]:
                    # remove the original curves for the replacement
                    vertices_list.remove(curve1)
                    vertices_list.remove(curve2)

                    curve2.reverse()

                    vertices_list.append(curve2[0:-1] + curve1)

                    # if the comparison curve comes before the reference curve, adjust the comparison curve location
                    if j < i:
                        i -= 1

                    # specify that two contours were merged
                    merged = True
                    break

                # if the curves share an endpoint, reverse the second one and join it with the first
                if curve1[-1] == curve2[-1]:
                    # remove the original curves for the replacement
                    vertices_list.remove(curve1)
                    vertices_list.remove(curve2)

                    curve2.reverse()

                    vertices_list.append(curve1[0:-2] + curve2)

                    # if the comparison curve comes before the reference curve, adjust the comparison curve location
                    if j < i:
                        i -= 1

                    # specify that two contours were merged
                    merged = True
                    break

                # if the curves share an opposite terminal point, join them
                if curve1[0] == curve2[-1]:
                    # remove the original curves for the replacement
                    vertices_list.remove(curve1)
                    vertices_list.remove(curve2)

                    vertices_list.append(curve2[0:-2] + curve1)

                    # if the comparison curve comes before the reference curve, adjust the comparison curve location
                    if j < i:
                        i -= 1

                    # specify that two contours were merged
                    merged = True
                    break

                # if the curves share an opposite terminal point, join them
                if curve1[-1] == curve2[0]:
                    # remove the original curves for the replacement
                    vertices_list.remove(curve1)
                    vertices_list.remove(curve2)

                    # if the comparison curve comes before the reference curve, adjust the comparison curve location
                    vertices_list.append(curve1[0:-1] + curve2)

                    if j < i:
                        i -= 1  # adjust index if we removed earlier item

                    # specify that two contours were merged
                    merged = True
                    break

            # look at the next curve to compare
            j += 1

        # if no merge was accomplished with the reference curve, move to the next one. Otherwise the index will stay the same becuase the reference curve has been removed.
        if not merged:
            i += 1

    return vertices_list


def get_vertices(msp, layer_name):
    '''
    ezdxf.layouts.layout.Modelspace, str -> list(list(tuple))

    Returns a list of lists of vertices for each contour in the layer
    '''
    # init a list to store vertices of each contour
    vertices_list = []

    # init a list to find which entity types need to be considered
    entity_types_present = []

    # iterate through each entity in the selected layer and add to the list
    for entity in msp.query(f'*[layer == "{layer_name}"]'):
        entity_types_present.append(entity.dxftype())

    # remove duplicates from the entity list to get a list of which entity types are present
    entity_types_present = list(set(entity_types_present))

    # look at each entity type
    for entity_type in entity_types_present:

        if entity_type == 'LINE':
            # add each line to the vertices_list as an independent contour
            for line in msp.query(f'LINE [layer == "{layer_name}"]'):
                vertices_list.append([(line.dxf.start.x,
                                       line.dxf.start.y),
                                      (line.dxf.end.x,
                                       line.dxf.end.y)])

        if entity_type == 'POLYLINE':
            # Query the polyline entities in the selected layer
            for contour in msp.query(f'POLYLINE [layer == "{layer_name}"]'):
                # Create a accumulator for the vertices set for this contour
                vertices_accum = []

                # Add each vertex to the accumulator
                for vertex in contour.vertices:
                    vertices_accum.append((vertex.dxf.location.x, vertex.dxf.location.y))

                # After each vertex for a contour is accumulated, add them to the vertices_list as a list
                vertices_list.append(vertices_accum)

        if entity_type == 'LWPOLYLINE':
            # Query the LWPOLYLINE entities in the selected layer
            for contour in msp.query(f'LWPOLYLINE [layer == "{layer_name}"]'):
                # Create a accumulator for the vertices set for this contour
                vertices_accum = []

                # Add each vertex to the accumulator
                for vertex in contour.vertices():
                    vertices_accum.append((float(vertex[0]), float(vertex[1])))

                # After each vertex for a contour is accumulated, add them to the vertices_list as a set
                vertices_list.append(vertices_accum)

        if entity_type in ['CIRCLE', 'ARC', 'SPLINE', 'ELLIPSE']:
            # look at each individual curve
            for curve in msp.query(f'CIRCLE ARC SPLINE ELLIPSE [layer == "{layer_name}"]'):
                # make a list to store the coordinates of each individual curve
                sub_list = []

                # slice the curve with the specified slice length
                for point in curve.flattening(slice_length):
                    # add each coordinate to the sub_list, rounding to ensure that coincident points are treated as such
                    sub_list.append((round(point.x, round_digits), round(point.y, round_digits)))

                vertices_list.append(sub_list)

    # ensure that contours are not double counted in the vertices_list
    unique_list = []
    for item in vertices_list:
        if item not in unique_list:
            unique_list.append(item)

    # stitch together connected curves and separate independent contours
    sorted_list = sort_curves(unique_list)

    # remove the outer list brackets as long as the vertices_list has one element and is not in the 'INNER' layer
    if len(sorted_list) == 1 and layer_name != 'INNER':
        return sorted_list[0]

    else:
        return sorted_list


def get_ply_number(filename, ply_prefix):
    '''
    str, str -> str

    Takes the current filename and the desired ply number start prefix and returns a number for the current ply

    Raises an exception if:
      - filename not of type str
      - ply_prefix not in filename
    '''
    assert type(filename) == str, 'get_ply_number expects object of type str'
    assert ply_prefix in filename, 'input filename does not contain ply_prefix'

    # Create a pattern that captures the digits after the layer_prefix
    pattern = fr"{re.escape(ply_prefix)}(\d+)"

    # Search for that pattern in the string
    match = re.search(pattern, filename)

    return str(int(match.group(1)))

assert get_ply_number('SHEAS STACKING_L1_BTMS 1025, TY 57, GR 48, CL E, FR 108 A.1_0_prd-BT-06172794.dxf', 'L') == '1'


def get_aspect_ratio(line1_text, line2_text, line_space, padding):
    '''
    str, str, float, float -> float

    Find the aspect ratio of a rectangle to fit the inputted text in two lines
    '''
    # get aspect ratio of line1_text and line2_text assuming char aspect ratio = 1
    line1_ratio = len(line1_text) * char_ratio
    line2_ratio = len(line2_text) * char_ratio

    # compute and return the ratio between the length elements (text lengt, padding) and height elements (2x text height, padding, spacing)
    return (max([line1_ratio, line2_ratio]) + padding) / (2 + line_space + padding)


def get_grid(bounds, num_x, num_y):
    '''
    tuple, int, int -> np.array

    takes the bounds of a bounding box and generates a grid to fill the bounds
    '''
    # Input parameters
    x_range = (bounds[2], bounds[0])
    y_range = (bounds[3], bounds[1])

    # Generate linearly spaced coordinates
    x_coords = np.linspace(x_range[0], x_range[1], num_x)
    y_coords = np.linspace(y_range[0], y_range[1], num_y)

    # Create the grid of points
    grid_points = np.array([[x, y] for y in y_coords for x in x_coords])

    return(grid_points)


def get_bbox(polygon: Polygon):
    '''
    shapely.geometry.polygon.Polygon -> tuple

    Find the coordinates of the bounding box of the polygon
    '''
    x_min, y_min, x_max, y_max = polygon.bounds

    return x_max, y_max, x_min, y_min


def rect_check(ply_polygon, rectangle, ply_rosette, ply_markers):
    '''
    shapely.Polygon, shapely.Polygon, shapely.LineString, shapely.Linstring -> Boolean

    checks if the rectangle fits inside of the ply polygon and does not intersect with rosette or markers
    '''
    # assume intersection
    output = False

    # check if the polygon contains the rectangle
    if contains_properly(ply_polygon, rectangle):
        # check if the rectangle intersects with the rosette
        if not intersects(rectangle, ply_rosette):
            # check if the rectangle intersects with the markers
            if not intersects(rectangle, ply_markers):
                # if all this is true, set the output to true
                output = True

    return output


def get_rotated_rectangle(aspect_ratio, centroid, height, angle_degrees):
    '''
    float, tuple, float, float -> shapely.Polygon

    Makes a rectangular Polygon object based on the specifications
    '''
    # define centroid x and y components
    cx, cy = centroid
    h = height
    # calculate width based on height and aspect ratio
    w = h * aspect_ratio

    theta = math.radians(angle_degrees)  # Convert to radians

    # Unrotated rectangle corners centered at (0, 0)
    half_w, half_h = w / 2, h / 2
    corners = [
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h)
    ]

    # Rotate and translate each corner
    rotated_corners = []
    for x, y in corners:
        x_rot = x * math.cos(theta) - y * math.sin(theta)
        y_rot = x * math.sin(theta) + y * math.cos(theta)
        rotated_corners.append((x_rot + cx, y_rot + cy))

    return Polygon(rotated_corners), rotated_corners


def delete_all_text(msp):
    '''
    ezdxf.layouts.layout.Modelspace -> None

    Delete all TEXT and MTEXT entities from a modelspace or layout.
    '''
    for e in list(msp.query("TEXT MTEXT")):  # make a copy of list to avoid iteration issues
        msp.delete_entity(e)


def draw_rectangle(msp, corners):
    """
    Draws a rectangle in the given modelspace using ezdxf.

    Parameters
    ----------
    msp : ezdxf.layouts.Modelspace
        The modelspace to add the rectangle to.
    corners : tuple
        A tuple of four corner points, each as (x, y[, z]).
        Example: ((0,0), (10,0), (10,5), (0,5))
    """
    if len(corners) != 4:
        raise ValueError("You must provide exactly 4 corner points.")

    # Ensure RECTANGLE layer exists
    doc = msp.doc
    if "RECTANGLE" not in doc.layers:
        doc.layers.add("RECTANGLE")

    # Create a closed LWPolyline with the corners
    msp.add_lwpolyline(
        points=corners,
        dxfattribs={"layer": "RECTANGLE", "closed": True}
    )


def scale_text(rect_height, padding, line_space):
    '''
    float, float, float -> float
    calculates the height of text such that two lines fit inside a rectangle with padding and line spacing
    '''
    return (rect_height / (2 + line_space + padding))


def place_first_line_text(msp, locating_point, angle_deg, height, line_spacing, text="FIRST"):
    '''
    ezdxf.layouts.layout.Modelspace, tuple, float, float, float, str -> NONE

    Place a TEXT entity in DXF so that its bottom is centered and perpendicular
    to a line segment starting at locating_point with length 1/2 linspacing and angle specified.
    '''
    # offset the inputted angle to position the text correctly
    angle_deg += 90
    # define x and y components of locating point
    x0, y0 = locating_point
    # convert the adjusted angle to radians
    angle_rad = math.radians(angle_deg)
    # store the adjusted angle + 90 degrees to locate perpendicular features
    perp_angle_rad = math.radians(angle_deg + 90)

    # Step 1: line segment vector (angle from vertical)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)

    # add magnitude
    dx *= ((line_spacing / 2))
    dy *= ((line_spacing / 2))

    # End of the line segment
    x1 = x0 + dx
    y1 = y0 + dy

    # Step 2: find the line segment vector to offset based on text width
    dx = math.cos(perp_angle_rad)
    dy = math.sin(perp_angle_rad)

    # Half overall length of text entity
    dx *= (len(text) * height * char_ratio) / 2
    dy *= (len(text) * height * char_ratio) / 2

    # Text locating point
    x2 = x1 + dx
    y2 = y1 + dy

    # Step 3: text rotation angle (perpendicular to line segment)
    text_angle_deg = (angle_deg - 90)

    # Step 4: add TEXT entity
    text_entity = msp.add_text(
        text,
        dxfattribs={
            "height": height,
            "rotation": text_angle_deg,
            "insert": (x2, y2),
            "style": "STANDARD"
        }
    )


def place_second_line_text(msp, locating_point, angle_deg, height, line_spacing, text="FIRST"):
    '''
    ezdxf.layouts.layout.Modelspace, tuple, float, float, float, str -> NONE

    Place a TEXT entity in DXF so that its top is centered and perpendicular
    to a line segment starting at locating_point with length 1/2 linspacing and angle specified.

    **The line segment has reversed direction from place_first_line_text**
    '''
    angle_deg += 90
    x0, y0 = locating_point
    angle_rad = math.radians(angle_deg)
    perp_angle_rad = math.radians(angle_deg + 90)

    # Step 1: line segment vector (angle from vertical)
    dx = -math.cos(angle_rad)
    dy = -math.sin(angle_rad)

    # add magnitude, include text height
    dx *= ((line_spacing / 2) + height)
    dy *= ((line_spacing / 2) + height)

    # End of the line segment
    x1 = x0 + dx
    y1 = y0 + dy

    # Step 2: find the line segment vector to offset based on text width
    dx = math.cos(perp_angle_rad)
    dy = math.sin(perp_angle_rad)

    # Half overall length of text entity
    dx *= (len(text) * height * char_ratio) / 2
    dy *= (len(text) * height * char_ratio) / 2

    # Text locating point
    x2 = x1 + dx
    y2 = y1 + dy

    # Step 3: text rotation angle (perpendicular to line segment)
    text_angle_deg = (angle_deg - 90)

    # Step 4: add TEXT entity
    text_entity = msp.add_text(
        text,
        dxfattribs={
            "height": height,
            "rotation": text_angle_deg,
            "insert": (x2, y2),
            "style": "STANDARD"
        }
    )


def save_files_from_dict(folder_path, file_contents_dict):
    """
    Saves the contents of a dictionary to files in a specified folder.

    Args:
        folder_path (str): The path to the folder where files will be saved.
        file_contents_dict (dict): A dictionary where keys are filenames and values are the file contents.
    """
    # Ensure the folder exists. If not, create it.
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Created folder: '{folder_path}'")

    # Loop through each filename and its content in the dictionary
    for filename, content in file_contents_dict.items():
        file_path = os.path.join(folder_path, filename)

        try:
            # Write the content to the file in binary mode
            with open(file_path, 'wb') as f:
                f.write(content)
            print(f"Successfully saved {filename} to '{file_path}'")
        except IOError as e:
            print(f"Could not write file {filename}: {e}")


#----SCRIPT----

#----PARAMETER CONTROLS---- 
# define the directory folder for ply dxfs
file_path = '/Users/sheasmith/Documents/Plies_test'

# get the files
uploaded = store_files_in_dict(file_path)

# set the current directory
os.chdir(file_path)

# number of test grid points along the x-axis of the ply bounding box
num_x = 10

# number of test grid points along the y-axis of the ply bounding box
num_y = 10

# number of rectangle scale stages
scale_resolution = 30

# number of rectangle angle stages
angle_resolution = 30

# written on the first line of text on each ply
line1_text = input("First line text (Digits following L will be replaced by ply number from filenames):")

# ply prefix that will be used to find the ply number
ply_prefix = input("ply prefix in filenames(e.g. 'L'):")

# written on the second line of text on each ply
line2_text = input("Second line text:")

# padding between text fit rectangle and text
padding = 0.5

# linespacing
line_space = 0.1

# max text height
max_text_height = 1

# character aspect ratio
char_ratio = 0.77

# Tell the script which layer names are required to process a ply
required_layers = ['OUTER', 'ROSETTE']

# Tell the script how small to make curve slices
slice_length = 1

# Tell the script how many digits should be considered when comparing point locations
round_digits = 6

#----ITERATE OVER EACH FILE----
# Grab each file from the upload by its filename
for filename in uploaded.keys():
    # define the dxf document and modelspace
    doc = ezdxf.readfile(filename)
    msp = doc.modelspace()

    # ensure the file contains the specified layers
    check_layers(msp, required_layers)

    # define the ply polygon in shapely (still works if INNER isn't present)
    ply_polygon = Polygon(get_vertices(msp, 'OUTER'), get_vertices(msp, 'INNER'))

    # define the ply rosette in shapely
    ply_rosette = LineString(get_vertices(msp, 'ROSETTE'))

    # define the ply markers in shapely (if they aren't present, still run this step)
    ply_markers = LineString(get_vertices(msp, 'MARKERS'))

    # define the line1 and line2 text
    this_line1_text = line1_text + get_ply_number(filename, ply_prefix)
    this_line2_text = line2_text

    # based on the text, find the aspect ratio of the fitting rectangle
    aspect_ratio_to_use = get_aspect_ratio(this_line1_text, this_line2_text, line_space, padding)

    #----NESTING LOOP----
    running_max = 0
    # for every point in the specified grid...
    for point in get_grid(get_bbox(ply_polygon),
                          num_x,
                          num_y):
        #...try rectangles with a bunch of scales...
        for rect_height in np.linspace(0.51,
                                       math.sqrt(ply_polygon.area),
                                       scale_resolution):
            #...and a bunch of angles
            for angle in np.linspace(0,
                                     180,
                                     angle_resolution):
                # if the rectangle fits and is larger than previous largest option,
                # make it the new largest option
                if rect_check(ply_polygon,
                              get_rotated_rectangle(aspect_ratio_to_use,
                                                    tuple(point),
                                                    rect_height,
                                                    angle)[0],
                              ply_rosette,
                              ply_markers
                              ) and rect_height > running_max:
                    running_max = rect_height
                    best_config = [point,
                                   rect_height,
                                   angle]
                    continue

    # remove all text from the file
    delete_all_text(msp)

    # optionally, draw the fitting rectangle on the dxf for debugging use
    # draw_rectangle(msp, get_rotated_rectangle(aspect_ratio_to_use, best_config[0], best_config[1], best_config[2])[1])

    # make the text as specified by the nesting loop unless its larger than 1 inch
    if scale_text(best_config[1], padding, line_space) > 1:
        # if fitting rectangle can accomodate text larger than 1 inch, make the text 1 inch and put it at centroid
        text_height = 1
    else:
        text_height = scale_text(best_config[1], padding, line_space)

    # place the text
    place_first_line_text(msp,
                          best_config[0],
                          best_config[2],
                          text_height,
                          line_space,
                          text=this_line1_text)

    place_second_line_text(msp,
                           best_config[0],
                           best_config[2],
                           text_height,
                           line_space,
                           text=this_line2_text)

    # save the file
    doc.saveas(filename)

print('DONE.')
