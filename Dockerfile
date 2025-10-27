# Use the official Python 3.11-slim image as the base image.
FROM python:3.11-slim

# Set the working directory inside the container to /app.
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt /app/
COPY mcp_server/requirements.txt /app/mcp_server/

# Install required Python packages from requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r mcp_server/requirements.txt

# Copy all files from the current directory into /app in the container.
COPY . /app

# Cloud Run provides PORT environment variable, default to 8081
ENV PORT=8081

# Expose port 8081 (Cloud Run default)
EXPOSE 8081

# Define the command to run your SSE server.
# Use PORT environment variable for Cloud Run compatibility
CMD python -m mcp_server.sse_server --host 0.0.0.0 --port ${PORT}