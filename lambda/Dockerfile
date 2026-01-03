# Use Python 3.11 slim image to avoid numpy conflicts
FROM python:3.11-slim

# Set working directory
WORKDIR /var/task

# Force rebuild - v2.0.1
RUN echo "Config version 2.0.1" > /tmp/version.txt

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY lambda/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install AWS Lambda Runtime Interface Client
RUN pip install awslambdaric

# Copy function code and config
COPY lambda/ .
COPY config/ ./config/

# Set the Lambda runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["index.lambda_handler"]
