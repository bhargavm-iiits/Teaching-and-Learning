# Dockerfile

# Use an official lightweight Python image as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed by some Python packages
# This is a good practice for ensuring a stable environment
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker's build cache
# This layer is only rebuilt if requirements.txt changes
COPY requirements.txt requirements.txt

# Install the Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
# This includes main.py and the 'agents' directory
COPY . .

# The command to run your application
# Uvicorn will run on host 0.0.0.0 and use the port specified
# by the PORT environment variable, which Cloud Run provides automatically.
ENV PORT=8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]