import cv2

def apply_effect_frame(frame):
    """
    Zoom/crop the frame to hide a logo or watermark.

    This example crops 70 pixels from the bottom (where a watermark 
    might be located) and then resizes back to the original size 
    so the video maintains its dimensions.
    """
    h, w, _ = frame.shape

    # --- Crop parameters ---
    crop_x_start = 0
    crop_y_start = 0
    crop_x_end   = w
    crop_y_end   = h - 70   # hide bottom 70 pixels

    # --- Crop the region of interest ---
    cropped = frame[crop_y_start:crop_y_end, crop_x_start:crop_x_end]

    # --- Resize back to original dimensions ---
    resized = cv2.resize(cropped, (w, h))

    return resized
