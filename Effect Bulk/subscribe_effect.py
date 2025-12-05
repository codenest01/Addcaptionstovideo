import cv2
import os
import imageio
import random
import json

# ------------------------------------------------------------------
# Correctly determine the GIF folder location (SubscribeEmoji folder)
# ------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)  # Go up one level from "Effect Bulk"
GIF_FOLDER = os.path.join(PROJECT_ROOT, "SubscribeEmoji")

# Usage tracking file inside the GIF folder
USAGE_FILE = os.path.join(GIF_FOLDER, "gif_usage.json")

# Video settings
VIDEO_WIDTH = 1280
TARGET_RATIO = 0.25  # GIF will be 25% of video width


# ------------------------------------------------------------------
# Load and preprocess all GIFs once at startup
# ------------------------------------------------------------------
def load_gifs(folder, video_width, ratio=0.25):
    gifs = {}
    if not os.path.exists(folder):
        print(f"⚠️ GIF folder not found: {folder}")
        return gifs

    print(f"Loading GIFs from: {folder}")
    for file in os.listdir(folder):
        if not file.lower().endswith(".gif"):
            continue

        path = os.path.join(folder, file)
        try:
            gif_reader = imageio.get_reader(path)
            frames_raw = [frame for frame in gif_reader]

            target_width = int(video_width * ratio)
            frames = []
            for frame in frames_raw:
                # Convert to BGRA (OpenCV format with alpha)
                if frame.shape[2] == 4:  # Already has alpha
                    frame_rgba = frame
                else:
                    frame_rgba = cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA)

                frame_bgra = cv2.cvtColor(frame_rgba, cv2.COLOR_RGBA2BGRA)
                scale = target_width / frame_bgra.shape[1]
                target_height = int(frame_bgra.shape[0] * scale)
                resized = cv2.resize(frame_bgra, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
                frames.append(resized)

            gifs[file] = frames
            print(f"   Loaded: {file} ({len(frames)} frames)")
        except Exception as e:
            print(f"❌ Failed to load {file}: {e}")

    return gifs


ALL_GIFS = load_gifs(GIF_FOLDER, VIDEO_WIDTH, TARGET_RATIO)

# ------------------------------------------------------------------
# JSON usage persistence (to avoid repeating the same GIF too often)
# ------------------------------------------------------------------
def load_usage():
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load usage file: {e}")
    return {"used": [], "video_map": {}}


def save_usage(data):
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save usage file: {e}")


USAGE_DATA = load_usage()


# ------------------------------------------------------------------
# Pick a GIF fairly (round-robin + persistence per video)
# ------------------------------------------------------------------
def pick_gif_for_video(video_id="default"):
    # Return already assigned GIF for this video
    if video_id in USAGE_DATA.get("video_map", {}):
        name = USAGE_DATA["video_map"][video_id]
        return ALL_GIFS.get(name, random.choice(list(ALL_GIFS.values())) if ALL_GIFS else [])

    all_names = list(ALL_GIFS.keys())
    if not all_names:
        return []  # No GIFs loaded

    used = set(USAGE_DATA.get("used", []))

    # Reset cycle if we've used all
    if len(used) >= len(all_names):
        USAGE_DATA["used"] = []
        used = set()

    available = [n for n in all_names if n not in used]
    if not available:
        available = all_names

    chosen_name = random.choice(available)
    USAGE_DATA.setdefault("used", []).append(chosen_name)
    USAGE_DATA.setdefault("video_map", {})[video_id] = chosen_name
    save_usage(USAGE_DATA)

    return ALL_GIFS[chosen_name]


# ------------------------------------------------------------------
# Alpha overlay helper
# ------------------------------------------------------------------
def overlay_transparent(background, overlay, x, y):
    h, w = overlay.shape[:2]

    # Boundary check
    if y + h > background.shape[0] or x + w > background.shape[1] or y < 0 or x < 0:
        return

    alpha = overlay[:, :, 3] / 255.0
    for c in range(3):
        background[y:y+h, x:x+w, c] = (
            alpha * overlay[:, :, c] +
            (1 - alpha) * background[y:y+h, x:x+w, c]
        )


# ------------------------------------------------------------------
# Main function to apply the subscribe/reminder GIF effect
# ------------------------------------------------------------------
def apply_effect_frame(frame, frame_idx, fps=30, video_id="default"):
    if not ALL_GIFS:
        return frame

    gif_frames = pick_gif_for_video(video_id)
    if not gif_frames:
        return frame

    total_gif_frames = len(gif_frames)

    # Show GIF from 1 second to 6 seconds (5 seconds duration)
    start_sec = 1.0
    duration_sec = 5.0
    current_sec = frame_idx / fps

    if current_sec < start_sec:
        return frame

    elapsed_in_effect = current_sec - start_sec
    if elapsed_in_effect > duration_sec:
        return frame

    # Calculate which GIF frame to show
    gif_idx = int((elapsed_in_effect / duration_sec) * total_gif_frames) % total_gif_frames
    overlay = gif_frames[gif_idx]

    # Position: bottom-right with 12px padding
    pad = 12
    x = frame.shape[1] - overlay.shape[1] - pad
    y = frame.shape[0] - overlay.shape[0] - pad

    overlay_transparent(frame, overlay, x, y)
    return frame
