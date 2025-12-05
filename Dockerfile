FROM python:3.10-slim

# Install system dependencies for OpenCV + Whisper + audio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# You have TWO workers. Railway will choose the correct Procfile.
CMD ["sh", "-c", "echo 'Use Procfile to run workers on Railway'"]
