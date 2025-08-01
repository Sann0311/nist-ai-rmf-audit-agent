# Use the official lightweight Python image.
FROM python:3.10-slim

# Set working directory
WORKDIR /app

RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    fastapi uvicorn[standard] httpx

# Copy your application code
COPY . .

# Expose port 8001
EXPOSE 8001

# Set timezone
ENV TZ=America/Toronto
RUN apt-get update && apt-get install -y tzdata netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Run Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]