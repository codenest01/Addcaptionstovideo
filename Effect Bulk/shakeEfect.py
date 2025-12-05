import cv2
import numpy as np
import math
import os
import json
import random
import itertools

USAGE_FILE = os.path.join(os.path.dirname(__file__), "effect_usage.json")

# ---- Define base effects ----
BASE_EFFECTS = ["zoom", "pan", "float", "rotate", "diag_pan", "diag_float", "spiral", "pulse_zoom"]

# Generate all unique combos (1–4 effects)
EFFECT_COMBOS = []
for r in range(1, 5):
    for combo in itertools.combinations(BASE_EFFECTS, r):
        EFFECT_COMBOS.append(list(combo))

# Shuffle so it doesn’t always start with the same order
random.shuffle(EFFECT_COMBOS)

# -----------------------------
# JSON persistence
# -----------------------------
def load_usage():
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"used": [], "video_map": {}}
    return {"used": [], "video_map": {}}

def save_usage(data):
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)

USAGE_DATA = load_usage()

def pick_effect_for_video(video_id):
    if video_id in USAGE_DATA["video_map"]:
        return USAGE_DATA["video_map"][video_id]

    used = [tuple(e) for e in USAGE_DATA["used"]]

    if len(used) >= len(EFFECT_COMBOS):
        USAGE_DATA["used"] = []
        used = []

    available = [combo for combo in EFFECT_COMBOS if tuple(combo) not in used]
    chosen = random.choice(available)

    USAGE_DATA["used"].append(chosen)
    USAGE_DATA["video_map"][video_id] = chosen
    save_usage(USAGE_DATA)
    return chosen

# -----------------------------
# Normal-speed, professional motion
# -----------------------------
def apply_effect_frame(frame, frame_idx, fps=30, video_id="default"):
    h, w = frame.shape[:2]
    t = frame_idx / fps

    chosen_effects = pick_effect_for_video(video_id)

    # Identity transform
    M_total = np.eye(3)

    # ----- ZOOM -----
    if "zoom" in chosen_effects:
        zoom_factor = 1 + 0.01 * math.sin(2 * math.pi * 0.1 * t)  # ±1%
        M_zoom = cv2.getRotationMatrix2D((w//2, h//2), 0, zoom_factor)
        M_zoom = np.vstack([M_zoom, [0,0,1]])
        M_total = M_zoom @ M_total

    # ----- PULSE ZOOM -----
    if "pulse_zoom" in chosen_effects:
        zoom_factor = 1 + 0.02 * abs(math.sin(2 * math.pi * 0.25 * t))  # ±2%
        M_pulse = cv2.getRotationMatrix2D((w//2, h//2), 0, zoom_factor)
        M_pulse = np.vstack([M_pulse, [0,0,1]])
        M_total = M_pulse @ M_total

    # ----- PAN (x shift) -----
    if "pan" in chosen_effects:
        dx = int(12 * math.sin(2 * math.pi * 0.06 * t))  # ~12px
        M_pan = np.array([[1,0,dx],[0,1,0],[0,0,1]], dtype=float)
        M_total = M_pan @ M_total

    # ----- FLOAT (y shift) -----
    if "float" in chosen_effects:
        dy = int(10 * math.sin(2 * math.pi * 0.06 * t))  # ~10px
        M_float = np.array([[1,0,0],[0,1,dy],[0,0,1]], dtype=float)
        M_total = M_float @ M_total

    # ----- DIAGONAL PAN -----
    if "diag_pan" in chosen_effects:
        shift = int(12 * math.sin(2 * math.pi * 0.05 * t))  # ~12px
        M_diag_pan = np.array([[1,0,shift],[0,1,shift],[0,0,1]], dtype=float)
        M_total = M_diag_pan @ M_total

    # ----- DIAGONAL FLOAT -----
    if "diag_float" in chosen_effects:
        shift = int(10 * math.sin(2 * math.pi * 0.07 * t))  # ~10px
        M_diag_float = np.array([[1,0,-shift],[0,1,shift],[0,0,1]], dtype=float)
        M_total = M_diag_float @ M_total

    # ----- ROTATE -----
    if "rotate" in chosen_effects:
        angle = 2.0 * math.sin(2 * math.pi * 0.04 * t)  # ±2 degrees
        M_rot = cv2.getRotationMatrix2D((w//2, h//2), angle, 1)
        M_rot = np.vstack([M_rot, [0,0,1]])
        M_total = M_rot @ M_total

    # ----- SPIRAL (zoom + rotate) -----
    if "spiral" in chosen_effects:
        angle = 3.0 * math.sin(2 * math.pi * 0.03 * t)  # ±3 degrees
        zoom_factor = 1 + 0.005 * t  # steady zoom
        M_spiral = cv2.getRotationMatrix2D((w//2, h//2), angle, zoom_factor)
        M_spiral = np.vstack([M_spiral, [0,0,1]])
        M_total = M_spiral @ M_total

    # Apply once
    M_affine = M_total[:2]
    frame = cv2.warpAffine(frame, M_affine, (w, h), borderMode=cv2.BORDER_REFLECT)

    return frame
