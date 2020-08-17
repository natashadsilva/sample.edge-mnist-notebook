import numpy as np
from PIL import Image, ImageOps

# Compute the pixel center of mass of a given image, stored in a 2-D numpy array.
def computeCOM(i):
    xsum = 0
    ysum = 0
    msum = 0
    height, width = i.shape
    for x in range(width):
        for y in range(height):
            msum += i[y][x]
            xsum += x*i[y][x]
            ysum += y*i[y][x]
    if msum > 0:
        return (xsum/msum, ysum/msum)
    else:
        # For empty images, return the center, I guess
        return (width/2, height/2)
    
    
# Prepare the image to be scored.
# The MNIST data set of digits we're using is normalized so the digit occupies
# a 20x20 grid, centered by pixel-mass in a 28x28 canvas.
# Overscan would reserve edge pixels in the 20x20 grid for some border, but this isn't necessary.
def image_prep(image, intermediate_size=20, target_size= 28, overscan_pixels=0):
    inverted_image = file_loaded_preprep(image)
    small_image = square_fit_resize(inverted_image, intermediate_size=intermediate_size, overscan_pixels=overscan_pixels)
    target_image = center_by_pixel_mass(small_image, target_size=target_size)
    
    return np.array(target_image), small_image, inverted_image


# The digits dataset included in sklearn is already pre-processed, but not in
# a way compatible with the MNIST dataset.  First, we need to load the data into
# a PIL compatible Image object, and correct the grayscale data from 0-16 to
# 0-255.  No inversion is necessary, since its already set up with 0 as white/
# background and 16 (full scale) as full black.
def sklearn_digit_preprep(image):
    return Image.fromarray(image * 255 / 16)

# When using PIL.Image.open() to load a PNG file image, we need to convert to
# greyscale and invert, to get the pixel data into the form we can use for later
# processing. (0-255, where 0 is white/background and 255 is full black)
def file_loaded_preprep(image):
    return ImageOps.invert(image.convert("L"))

# After bringing in the image to the PIL Image format and getting the greyscale
# correct, we need to crop and pad the image such that it is the smallest square
# canvas that fits the image data, then resize that image down (or up!) to an
# intermediate size appropriate for our training set.  In our case, MNIST is
# trained on 20x20 pixel digit images. Optionally, we can include some overscan
# space around the image inside that 20x20 canvas, but this is not necessary
# when using the MNIST training set.
def square_fit_resize(image, intermediate_size=20, overscan_pixels=0):
    # Compute the bounding box of the actual content of the image, so we can ensure
    # the source image is in a square canvas, preserving aspect ratio, before resizing.
    bb = image.getbbox()
    if bb is not None:
        width = bb[2] - bb[0]
        height = bb[3] - bb[1]
        maxd = max(width, height)
        excess_w = maxd - width
        excess_h = maxd - height
        new_left = bb[0] - excess_w//2
        new_top = bb[1] - excess_h//2

        # Rough computation of excess pixels to keep around the bounded digit, if desired.
        overscan = int(overscan_pixels * round(maxd/intermediate_size))

        # Crop the image to just contain the desired digit pixels, in a square canvas, with any "overscan" border included
        cropped_image = image.crop((new_left - overscan, new_top - overscan, new_left + maxd + overscan, new_top + maxd + overscan))
    
        # Resize the square/cropped image down to the intermediate size, using LANCZOS resampling (adding anti-aliasing pixels where useful)
        return cropped_image.resize((intermediate_size,intermediate_size), resample=Image.LANCZOS)
    else:
        # Nothing in this image, so just create an empty image of the intermediate_size
        return Image.new('L', (intermediate_size, intermediate_size), color=0)
    
# For the final bit of pre-processing, we need to center the intermediate image
# into a slightly larger canvas, translating the pixel-center-of-mass to the
# center of the target canvas.  The MNIST training data was all preprocessed
# this way, so we need to match that when predicting on new test data.
def center_by_pixel_mass(image, target_size=28):
    # Compute the pixel-center-of-mass of the reduced image,
    # and allowing us to determine where to place the reduced image in the target canvas (slightly larger than the reduced image size).
    image_array = np.array(image)
    (com_x, com_y) = computeCOM(image_array)
    new_origin = (int(round(target_size / 2 - com_x)), int(round(target_size/2 - com_y)))
    
    # Create a new, empty canvas of the target size
    target_image = Image.new('L', (target_size,target_size), color=0)
    
    # Paste in the reduced image of the digit into the target canvas, at an appropriate location so the pixel-center-of-mass
    # of the final image is centered in the canvas.
    target_image.paste(image, box=new_origin)
    
    return target_image
  
  