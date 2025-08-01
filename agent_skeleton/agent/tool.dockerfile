# Base Python image
FROM python:3.10-slim

# Set common environment variables
ENV TF_CPP_MIN_LOG_LEVEL=3
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
ENV TF_GPU_ALLOCATOR=cuda_malloc_async
ENV HF_TOKEN=""
ENV TZ=America/Toronto

# Update pip and install base dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    google-adk litellm \
    grpcio-status==1.48.2

# Install required packages for the audit agent
RUN pip install --no-cache-dir \
    pandas==2.2.0 \
    openpyxl==3.1.2 \
    streamlit==1.28.0 \
    fastapi==0.104.0 \
    uvicorn==0.24.0 \
    httpx==0.25.0 \
    python-multipart==0.0.6 \
    jmespath \
    fix-busted-json==0.0.18

# Create app directory
WORKDIR /app

# Copy the audit data file
COPY multi_tool_agent/app/Audit.xlsx /app/Audit.xlsx

# Remove any tool-specific cache after install
RUN rm -rf /root/.cache/pip

# Copy backend code
COPY ./multi_tool_agent /workspace/multi_tool_agent

# Copy the simple agent server
COPY ./simple_agent_server.py /workspace/simple_agent_server.py

# Copy ADK configuration
COPY ./adk.yaml /workspace/adk.yaml

# Install tzdata for timezone support and curl for healthcheck
RUN apt-get update && apt-get install -y tzdata curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Expose ADK API port
EXPOSE 8000

# Start the simple agent server directly
ENTRYPOINT ["python", "simple_agent_server.py"]

# Usage (example):
# docker run --rm --gpus all -p 8000:8000 [image-name]
