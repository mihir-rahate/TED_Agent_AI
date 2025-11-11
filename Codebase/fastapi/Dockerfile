# # Dockerfile for FastAPI
# FROM python:3.10-slim

# # Set working directory
# WORKDIR /app

# # Install system-level dependencies
# RUN apt-get update && apt-get install -y \
#     libxml2-dev \
#     libxslt-dev \
#     libgraphviz-dev \
#     graphviz \
#     build-essential \
#     libodbc1 \
#     odbcinst \
#     odbcinst1debian2 \
#     unixodbc \
#     unixodbc-dev \
#     && apt-get clean

# # Install Python dependencies
# COPY requirements.txt /requirements.txt
# RUN pip install --no-cache-dir -r /requirements.txt

# # Copy application code
# COPY . .

# # Expose the application port
# EXPOSE 8000

# # Command to run the FastAPI application
# CMD ["uvicorn", "fastapi_main:app", "--host", "0.0.0.0", "--port", "8000"]


##########################
# Dockerfile for FastAPI
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system-level dependencies (UPDATED - removed problematic packages)
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    libgraphviz-dev \
    graphviz \
    build-essential \
    unixodbc \
    unixodbc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the application port
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "fastapi_main:app", "--host", "0.0.0.0", "--port", "8000"]