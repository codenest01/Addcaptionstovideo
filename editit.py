import os                                                              
import cv2                                                             
import glob
import subprocess
import importlib.util                                                  
import inspect
import random
import uuid
import whisper
import srt
import re
import time 
from datetime import timedelta
import sys # NEW: Import sys for flushing/single-line printing

# --- Configuration ---
MAX_EDIT_RETRIES = 3 # NEW: Max retries for the entire video creation process
LOG_CLEANUP_INTERVAL = 20 # NEW: Number of videos to process before clearing the console

# Directories
base_dir = os.path.dirname(os.path.abspath(__file__))                  
audio_dir = os.path.join(base_dir, 'audio')
image_dir = os.path.join(base_dir, 'images')
output_dir = os.path.join(base_dir, 'output')                          
subscribe_gif_dir = os.path.join(base_dir, 'SubscribeEmoji')           
effects_dir = os.path.join(base_dir, 'Effect Bulk')

os.makedirs(output_dir, exist_ok=True)
os.makedirs(audio_dir, exist_ok=True) 
os.makedirs(image_dir, exist_ok=True) 

# Check GIF folder
if not os.path.exists(subscribe_gif_dir):                                  
    print(f"⚠️ GIF folder not found: {subscribe_gif_dir}")
else:                                                                      
    print(f"✅ GIF folder found: {subscribe_gif_dir}")
# -----------------------                                              
# Load effect modules dynamically
# -----------------------                                              
def load_effect_modules():
    modules = []
    for effect_file in glob.glob(os.path.join(effects_dir, "*.py")):
        name = os.path.splitext(os.path.basename(effect_file))[0]
        try:
            spec = importlib.util.spec_from_file_location(name, effect_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "apply_effect_frame"):
                modules.append(module.apply_effect_frame)
            else:
                print(f"⚠️ Skipping {effect_file} (no apply_effect_frame function)")
        except Exception as e:
            print(f"❌ Failed to load effect module {name}: {e}")
    return modules

effects_list = load_effect_modules()

# -----------------------
# Unique random video name
# -----------------------
def get_random_video_name(output_dir, prefix="video_", ext=".mp4"):
    unique_id = uuid.uuid4().hex[:8]
    return os.path.join(output_dir, f"{prefix}{unique_id}{ext}")

# -----------------------
# Subtitle Generation (with safe filename)
# -----------------------
def generate_srt(audio_path, model_size="tiny"):
    """Generates an SRT subtitle file from an audio file using OpenAI's Whisper."""
    print("🚀 Generating subtitles with Whisper...")

    raw_srt_path = os.path.splitext(audio_path)[0] + ".srt"

    try:
        model = whisper.load_model(model_size)
        result = model.transcribe(audio_path, verbose=False)
        subtitles = []

        for i, seg in enumerate(result["segments"]):
            start = timedelta(seconds=seg["start"])
            end = timedelta(seconds=seg["end"])
            text = seg["text"].strip()
            subtitles.append(srt.Subtitle(index=i+1, start=start, end=end, content=text))

        with open(raw_srt_path, "w", encoding="utf-8") as f:
            f.write(srt.compose(subtitles))

        # ---- SAFE RENAME STEP ----
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(raw_srt_path))
        safe_srt_path = os.path.join(os.path.dirname(raw_srt_path), safe_name)
        
        if os.path.exists(raw_srt_path) and raw_srt_path != safe_srt_path:
             os.rename(raw_srt_path, safe_srt_path)
        elif raw_srt_path != safe_srt_path:
             pass
        else:
             safe_srt_path = raw_srt_path

        print("✅ Subtitles saved:", safe_srt_path)

        return safe_srt_path

    except Exception as e:
        print(f"❌ Whisper transcription failed: {e}")
        return None

# -----------------------
# Main video creation function
# -----------------------
def create_video(image_path, audio_path, srt_path, output_path, fps=10):
    print(f"\n🎬 Starting video creation for: {os.path.basename(audio_path)}")

    # 1. Image and Dimensions
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Error: Image not found or could not be loaded: {image_path}")
        return False 

    h, w, _ = img.shape
    if w % 2 != 0: w -= 1
    if h % 2 != 0: h -= 1
    img = cv2.resize(img, (w, h))

    # 2. Get Audio Duration
    try:
        cmd_duration = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
        ]
        result = subprocess.run(cmd_duration, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        duration = float(result.stdout.strip())
        total_frames = int(duration * fps)
        print(f"✅ Audio duration: {duration:.2f}s, Total frames to process: {total_frames}")
        if total_frames <= 0:
            print("⚠️ Warning: Audio duration is too short. Skipping video creation.")
            return False 
    except Exception as e:
        print(f"❌ Error getting audio duration with ffprobe: {e}. Stderr: {result.stderr if 'result' in locals() else 'N/A'}")
        return False 

    # 3. Subtitles
    video_filters = ""
    if srt_path and os.path.exists(srt_path):
        # FFmpeg filter style
        srt_path_ffmpeg = os.path.abspath(srt_path).replace("\\", "/")
        # Escaping colons for Windows paths in FFmpeg
        srt_path_ffmpeg = srt_path_ffmpeg.replace(":", "\\:")

        style_settings = (
            "Fontname=Arial,"
            "Fontsize=28,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H00000000,"
            "Bold=0,"
            "Outline=1,"
            "Shadow=1,"
            "Alignment=10,"   # Middle Center
        )
        subtitle_filter = f"subtitles='{srt_path_ffmpeg}':force_style='{style_settings}'"
        video_filters = subtitle_filter
        print("✅ Subtitles filter added.")
    else:
        print("⚠️ No valid SRT file provided. Video will not have captions.")


    # 4. FFmpeg command
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{w}x{h}',
        '-r', str(fps),
        '-i', 'pipe:0',
        '-i', audio_path,
    ]
    if video_filters:
        ffmpeg_cmd.extend(['-vf', video_filters])
    ffmpeg_cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-shortest',
        output_path
    ])

    process = None
    try:
        process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

        # 5. Write frames
        for frame_idx in range(total_frames):
            frame = img.copy()

            # Apply effects
            for effect in effects_list:
                try:
                    sig = inspect.signature(effect)
                    kwargs = {}
                    if "frame_idx" in sig.parameters: kwargs["frame_idx"] = frame_idx
                    if "fps" in sig.parameters: kwargs["fps"] = fps
                    if "video_id" in sig.parameters: kwargs["video_id"] = os.path.basename(output_path)
                    if "audio_name" in sig.parameters: kwargs["audio_name"] = os.path.splitext(os.path.basename(audio_path))[0]
                    frame = effect(frame, **kwargs)
                except Exception as e:
                    print(f"❌ Error applying effect {effect.__name__}: {e}")

            process.stdin.write(frame.tobytes())
            
            # Print progress on a single line
            if (frame_idx + 1) % fps == 0 or frame_idx == total_frames - 1:
                print(f"Processing frame {frame_idx+1}/{total_frames} ({((frame_idx+1)/total_frames)*100:.1f}%)", end="\r")
                sys.stdout.flush() # Ensure the output updates immediately

        # 6. Cleanup
        process.stdin.close()
        process.wait(timeout=30) 

        # Print final status message on a new line
        if process.returncode != 0:
            print(f"\n❌ FFmpeg failed with return code {process.returncode}.")
            return False

        print(f"\n🎉 Video created with {len(effects_list)} effects: {output_path}")
        return True 

    except subprocess.TimeoutExpired:
        print(f"\n❌ Error during FFmpeg cleanup: Process timed out.")
        if process: process.kill()
        return False
    except Exception as e:
        print(f"\n❌ Error during video processing: {e}")
        if process: process.kill()
        return False

# -----------------------
# Continuous batch process
# -----------------------
if __name__ == "__main__":
    
    # NEW: Counter for log cleanup
    processed_count = 0
    
    while True:
        # Get list of files to process
        images = sorted([os.path.join(image_dir, f) for f in os.listdir(image_dir) if f.lower().endswith(('.png','.jpg','.jpeg'))])
        audios = sorted([os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.lower().endswith(('.mp3','.flac','.wav','.aac'))])

        total_videos = min(len(images), len(audios))

        if total_videos == 0:
            # NEW: Single-line printing for the waiting message
            print(f"💤 No image/audio pairs found. Checking again in 10 seconds...", end="\r")
            sys.stdout.flush()
            time.sleep(10)
            continue 
        
        # Once files are found, print a new line over the waiting message
        print(f"\nFound {total_videos} pairs to process.") 
        
        # Process the first available pair
        img_path = images[0]
        aud_path = audios[0]
        
        # --- NEW: Retry Logic Loop ---
        attempt = 0
        video_success = False
        srt_file = None
        
        while attempt < MAX_EDIT_RETRIES:
            attempt += 1
            print(f"\n--- Processing Pair: {os.path.basename(img_path)} and {os.path.basename(aud_path)} (Attempt {attempt}/{MAX_EDIT_RETRIES}) ---")
            
            try:
                # 1. Generate Subtitles (Only do this once per audio)
                if attempt == 1:
                    srt_file = generate_srt(aud_path)
                    if not srt_file:
                        # If SRT fails on the first attempt, no need to retry video creation
                        print("❌ Subtitle generation failed. Cannot proceed with video.")
                        break # Break out of the retry loop

                # 2. Create Video
                out_file = get_random_video_name(output_dir, prefix="video_", ext=".mp4")
                video_success = create_video(img_path, aud_path, srt_file, out_file)
                
                if video_success:
                    break # Success! Break out of the retry loop

            except Exception as e:
                print(f"❌ An unhandled error occurred during attempt {attempt} for {os.path.basename(aud_path)}. Error: {e}")
                video_success = False
                
            # If failed, sleep before the next retry
            if not video_success and attempt < MAX_EDIT_RETRIES:
                print(f"⚠️ Video creation failed. Retrying in 5 seconds...")
                time.sleep(5)
                
        # --- End Retry Logic Loop ---


        # --- Final Cleanup ---
        
        # 3. Cleanup SRT
        if srt_file and os.path.exists(srt_file):
            os.remove(srt_file)
            print(f"🧹 Cleaned up temporary subtitle file: {srt_file}")

        # 4. Delete Source Files ONLY on final success or after max retries
        if video_success:
            processed_count += 1
            try:
                os.remove(aud_path)
                print(f"🗑️ Deleted source audio: {os.path.basename(aud_path)}")
                os.remove(img_path)
                print(f"🗑️ Deleted source image: {os.path.basename(img_path)}")
            except Exception as e:
                print(f"❌ Failed to delete source files {os.path.basename(aud_path)} and {os.path.basename(img_path)}: {e}")
        else:
            # Failed after MAX_EDIT_RETRIES attempts
            print(f"⚠️ Video creation failed after {MAX_EDIT_RETRIES} attempts. **Skipping and keeping** source files: {os.path.basename(aud_path)} and {os.path.basename(img_path)} for inspection.")

        
        # 5. Log Cleanup (NEW FEATURE)
        if processed_count >= LOG_CLEANUP_INTERVAL:
            print(f"\n\n=========================================")
            print(f"🧹 CLEARED LOGS AFTER {processed_count} SUCCESSFUL PROCESSES")
            print(f"=========================================\n\n")
            # This is a common way to clear the terminal screen
            # print('\033[H\033[J')
            processed_count = 0 


        # Continue to the next iteration immediately to check for the next pair
        # The 10-second delay is now only triggered when no files are found.
