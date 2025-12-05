import requests
import random
import os
import time
import json
from urllib.parse import quote

# --- Configuration ---
OPENROUTER_API_KEY = ""  # Your OpenRouter API Key
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Using a fast, capable model for prompt generation
OPENROUTER_MODEL = "openai/gpt-3.5-turbo"

# --- UPDATED SYSTEM MESSAGE ---
PROMPT_SYSTEM_MESSAGE = (
    "You are a creative prompt generator for high-resolution, cinematic AI images. "
    "Your output must be a single, highly detailed, visually descriptive prompt for an image "
    "that embodies the **Lofi, Chillhop, or Ambient music aesthetic**. Focus on elements like "
    "cozy rooms, rainy windows, neon lights, soft atmosphere, and cinematic depth. "
    "The prompt must be just the image description text, with absolutely no surrounding text, comments, or headings."
)

# --- Image Generation Settings ---
SAVE_FOLDER = "free_ultra_images"
WIDTH = 1920
HEIGHT = 1080
MODELS = [
    "flux",
    "anime",
    "sdxl",
    "revAnimated",
]

def get_openrouter_prompt():
    """Fetches a detailed Lofi/Cinematic image generation prompt from OpenRouter."""
    print("Requesting dynamic Lofi/Cinematic prompt from OpenRouter...")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        # These are required headers for OpenRouter
        "HTTP-Referer": "https://yourapp.com",  # Replace with your app's URL
        "X-Title": "Image Generator Script",  # Replace with your app's name
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEM_MESSAGE},
            # --- UPDATED USER MESSAGE to enforce Lofi theme ---
            {"role": "user", "content": "Generate a Lofi-style, cinematic, music-related background image prompt."},
        ],
        "temperature": 0.9, # Higher temperature for more creative prompts
        "max_tokens": 100, # Keep the prompt concise
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        result = response.json()

        # Extract the content, which should be the clean prompt text
        generated_prompt = result['choices'][0]['message']['content'].strip()
        return generated_prompt

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with OpenRouter: {e}")
        # Updated fallback prompt to match the new Lofi theme
        return "Cozy lofi study space, large window with rain, glowing desktop monitor, vinyl record player, volumetric lighting, ultra detailed, cinematic, 16:9"
    except (KeyError, IndexError) as e:
        print(f"Error parsing OpenRouter response: {e}")
        # Updated fallback prompt to match the new Lofi theme
        return "Anime girl relaxing by a neon-lit river at night, soft bokeh, chill atmosphere, high detail, 16:9"

def generate_image():
    if not os.path.exists(SAVE_FOLDER):
        os.makedirs(SAVE_FOLDER)

    # 1. Get the dynamic prompt from OpenRouter
    prompt = get_openrouter_prompt()

    # 2. Use a random model for image generation
    model = random.choice(MODELS)

    # Pollinations requires the prompt to be URL-encoded
    encoded_prompt = quote(prompt)

    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?model={model}&width={WIDTH}&height={HEIGHT}"
    )

    print(f"\nMODEL: {model}")
    print(f"GENERATED PROMPT: {prompt}")
    print("Generating image from Pollinations...")

    # 3. Call the Pollinations API to generate the image
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error generating image. Status code: {response.status_code}")
        print("Pollinations API Error:", response.text)
        return

    # 4. Save the generated image
    timestamp = int(time.time())
    # Create a simple, safe filename based on the prompt content
    safe_prompt_part = prompt[:30].replace(' ', '_').replace(',', '').lower()
    filename = f"{SAVE_FOLDER}/{safe_prompt_part}_{timestamp}.jpg"

    with open(filename, "wb") as f:
        f.write(response.content)

    print(f"✅ Successfully saved image: {filename}\n")


if __name__ == "__main__": # <-- FIX APPLIED HERE
    generate_image()
