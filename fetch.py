import os
import requests
import pymongo
import random
import time
import json
import sys # For flushing stdout and progress bar
from urllib.parse import quote
from pymongo.errors import ConnectionFailure, OperationFailure
from tqdm import tqdm # Import for progress bar

# --- Configuration ---
# --- MongoDB Configuration ---
MONGO_URI =  os.environ.get("MONGO_URI")
DATABASE_NAME = "songsdb"
COLLECTION_NAME = "generatedSongs"
OUTPUT_FOLDER = "audio"               # Final folder for song files
TEMP_FOLDER = "temp_downloads"         # Temp folder to prevent partial files
IMAGE_FOLDER = "images"               # Final folder for image files
MAX_SONG_DOWNLOAD_RETRIES = 3         # Max retries for song download
MAX_MONGO_CONNECT_RETRIES = 10        # Max retries for initial MongoDB connection
LOG_CLEANUP_INTERVAL = 20             # Number of documents to process before clearing the console

# --- OpenRouter/Pollinations Configuration for Image Generation ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-3.5-turbo" 

PROMPT_SYSTEM_MESSAGE = (
    "You are a creative prompt generator for high-resolution, cinematic AI images. "
    "Your output must be a single, highly detailed, visually descriptive prompt for an image "
    "that embodies the **Lofi, Chillhop, or Ambient music aesthetic**. Focus on elements like "
    "cozy rooms, rainy windows, neon lights, soft atmosphere, and cinematic depth. "
    "The prompt must be just the image description text, with absolutely no surrounding text, comments, or headings."
)

# Image Generation Settings
WIDTH = 1920
HEIGHT = 1080
MODELS = [
    "flux",
    "anime",
    "sdxl",
    "revAnimated",
]

# --- Helper Functions for Image Generation ---

def get_openrouter_prompt():
    """Fetches a detailed Lofi/Cinematic image generation prompt from OpenRouter, with unlimited retries."""
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://yourapp.com",
        "X-Title": "Lofi Content Worker",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEM_MESSAGE},
            {"role": "user", "content": "Generate a Lofi-style, cinematic, music-related background image prompt."},
        ],
        "temperature": 0.9,
        "max_tokens": 100,
    }

    while True: # Retry loop for OpenRouter/Image generation
        print("\n[PROMPT] Requesting dynamic Lofi/Cinematic prompt from OpenRouter...")
        try:
            response = requests.post(OPENROUTER_URL, headers=headers, data=json.dumps(payload), timeout=20)
            response.raise_for_status()

            result = response.json()
            generated_prompt = result['choices'][0]['message']['content'].strip()
            return generated_prompt

        except requests.exceptions.RequestException as e:
            print(f"❌ [ERROR] OpenRouter communication failure: {e}. Retrying in 5 seconds...")
        except (KeyError, IndexError) as e:
            print(f"❌ [ERROR] Error parsing OpenRouter response: {e}. Retrying in 5 seconds...")
        except Exception as e:
            print(f"❌ [ERROR] Unexpected OpenRouter error: {e}. Retrying in 5 seconds...")
        
        time.sleep(5)

def generate_and_save_image(base_filename: str):
    """Generates an image using Pollinations and saves it to the IMAGE_FOLDER, with unlimited retries."""
    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    
    while True: # Retry loop for image generation
        try:
            prompt = get_openrouter_prompt()
            model = random.choice(MODELS)
            encoded_prompt = quote(prompt)

            url = (
                f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                f"?model={model}&width={WIDTH}&height={HEIGHT}"
            )

            print(f"\n[IMAGE] Generation Details:")
            print(f"   MODEL: {model}")
            print(f"   PROMPT: {prompt}")
            print("   Generating image from Pollinations...")

            response = requests.get(url, timeout=40)
            response.raise_for_status()

            # Use the song filename but replace its extension with .jpg
            image_filename = os.path.splitext(base_filename)[0] + ".jpg"
            final_path = os.path.join(IMAGE_FOLDER, image_filename)

            with open(final_path, "wb") as f:
                f.write(response.content)

            print(f"✅ [IMAGE] Successfully saved: {final_path}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ [IMAGE] Pollinations error: {e}. Retrying image generation in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"❌ [IMAGE] Unexpected error in image process: {e}. Retrying in 5 seconds...")
            time.sleep(5)


# --- Core Download Logic ---

def fast_download_with_retry(url, final_path):
    """Download a file with a single-line progress bar and retries."""

    os.makedirs(TEMP_FOLDER, exist_ok=True)
    temp_path = os.path.join(TEMP_FOLDER, os.path.basename(final_path))
    
    for attempt in range(MAX_SONG_DOWNLOAD_RETRIES):
        print(f"\n[DOWNLOAD] Attempt {attempt + 1}/{MAX_SONG_DOWNLOAD_RETRIES}: Starting download...\n   URL: {url}")
        
        try:
            # 1. Start the request in stream mode
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)

                total_size_in_bytes = int(response.headers.get('content-length', 0))
                # Increased chunk size to 8MB for faster throughput
                block_size = 8 * 1024 * 1024 

                # 2. Use tqdm for the progress bar - CONFIGURATION FOR SINGLE LINE
                progress_bar = tqdm(
                    total=total_size_in_bytes, 
                    unit='iB', 
                    unit_scale=True, 
                    unit_divisor=1024,
                    desc="   Progress", 
                    ncols=80, 
                    file=sys.stdout,
                    leave=False # <--- KEY CHANGE: Ensures the bar stays on one line
                )
                
                with open(temp_path, 'wb') as temp_file:
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            temp_file.write(chunk)
                            progress_bar.update(len(chunk))
                
                progress_bar.close()

            # 3. Download successful, move file
            # The progress bar line is now gone/replaced by the following print.
            print("[DOWNLOAD] Finished. Moving to output folder...") 
            os.makedirs(OUTPUT_FOLDER, exist_ok=True)
            os.replace(temp_path, final_path)

            print(f"🎉 [DOWNLOAD] File saved successfully: {final_path}")
            return os.path.basename(final_path)

        except requests.exceptions.RequestException as e:
            print(f"❌ [DOWNLOAD] Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_SONG_DOWNLOAD_RETRIES - 1:
                print("   Retrying download in 3 seconds...")
                time.sleep(3)
            else:
                print(f"❌ [DOWNLOAD] Final attempt failed. Skipping this song.")
                # Clean up the failed temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return None
        except Exception as e:
            print(f"❌ [DOWNLOAD] Unexpected error: {e}")
            return None


# --- Server Worker Loop ---

def worker_loop():
    """The main infinite loop that checks for songs, processes them, and cleans up."""
    
    # 1. MongoDB Connection Setup with Retries
    client = None
    db = None
    collection = None
    
    for attempt in range(MAX_MONGO_CONNECT_RETRIES):
        try:
            print(f"Attempting to connect to MongoDB... ({attempt + 1}/{MAX_MONGO_CONNECT_RETRIES})")
            client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            
            print("=========================================")
            print("✅ Connected to MongoDB Atlas! Worker starting...")
            print("=========================================")
            db = client[DATABASE_NAME]
            collection = db[COLLECTION_NAME]
            break # Exit the retry loop on success

        except ConnectionFailure:
            print("❌ MongoDB connection error. Retrying in 5 seconds...")
            time.sleep(5)
        except OperationFailure as e:
            print(f"❌ MongoDB permission/operation error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"❌ Unexpected error during MongoDB connection: {e}. Retrying in 5 seconds...")
            time.sleep(5)
    else:
        # This code runs if all retries failed
        print("❌ CRITICAL: Failed to connect to MongoDB after multiple retries. Cannot start worker.")
        return

    # Initialize counter for log cleanup
    processed_count = 0
    
    # 2. Start the infinite loop
    while True:
        try:
            # 2a. Find and retrieve ONE document, including its unique ID
            doc = collection.find_one_and_update(
                {}, # Query: finds the first document
                {'$set': {'_status': 'processing'}}, 
                projection={"songUrl": 1},
                sort=[('_id', pymongo.ASCENDING)]
            )

            if not doc:
                print(f"\n[QUEUE] Database is empty. Checking again in 10 seconds...")
                time.sleep(10)
                continue 

            song_url = doc.get("songUrl")
            doc_id = doc.get("_id")

            if not song_url:
                print(f"🚨 [QUEUE] Document ID {doc_id} missing 'songUrl'. Deleting incomplete document.")
                collection.delete_one({"_id": doc_id})
                continue

            # 2b. Process: Download Song (with retry logic and progress bar)
            filename = song_url.split("/")[-1]
            final_audio_path = os.path.join(OUTPUT_FOLDER, filename)

            song_filename_base = fast_download_with_retry(song_url, final_audio_path)

            if not song_filename_base:
                # Download failed after all retries. Clean up DB record.
                print(f"❌ [PROCESS] Song download failed for {doc_id} after all retries. Deleting record.")
                collection.delete_one({"_id": doc_id})
                time.sleep(1)
                continue

            # 2c. Process: Generate Image (with infinite retry logic)
            image_success = generate_and_save_image(song_filename_base)

            if not image_success:
                 # Should only happen on a critical local I/O error, but included for completeness.
                print(f"⚠️ [PROCESS] Unrecoverable Image generation failure for {doc_id}. Deleting DB record.")
                collection.delete_one({"_id": doc_id})
                time.sleep(1)
                continue


            # 2d. Cleanup: Delete the processed document
            print(f"👍 [PROCESS] Completed task for ID {doc_id}. Deleting document from MongoDB.")
            collection.delete_one({"_id": doc_id})
            
            processed_count += 1
            
            # 2e. Log Cleanup
            if processed_count >= LOG_CLEANUP_INTERVAL:
                print(f"\n\n=========================================")
                print(f"🧹 CLEARED LOGS AFTER {processed_count} PROCESSES")
                print(f"=========================================\n\n")
                processed_count = 0

            # Short break before processing the next item to prevent API throttling
            print("-----------------------------------------")
            time.sleep(2)

        except pymongo.errors.PyMongoError as e:
            # Catch MongoDB specific errors that might occur during the loop (e.g., connection drop)
            print(f"❌ [WORKER ERROR] MongoDB operational error: {e}. Sleeping and continuing...")
            time.sleep(10)
        except requests.exceptions.RequestException as e:
            print(f"❌ [WORKER ERROR] HTTP/API communication error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"❌ [WORKER ERROR] Unexpected error in main loop: {e}")
            time.sleep(5)

    if client:
        client.close()
        print("🔒 MongoDB connection closed.")


if __name__ == "__main__":
    # NOTE: Ensure you have the required libraries installed:
    # pip install requests pymongo tqdm
    worker_loop()
