# Use the official camply Docker image with explicit platform
FROM --platform=linux/amd64 juftin/camply:latest

# Install AWS Lambda Runtime Interface Client and additional dependencies
COPY requirements.txt /tmp/
RUN pip install awslambdaric && \
    pip install -r /tmp/requirements.txt

# Set up writable cache directory and copy camply metadata
RUN mkdir -p /tmp/camply_cache/providers/usedirect/ReserveCalifornia && \
    cp -r /usr/local/lib/python3.11/site-packages/camply/providers/usedirect/ReserveCalifornia/* \
          /tmp/camply_cache/providers/usedirect/ReserveCalifornia/ 2>/dev/null || true

# Set up Lambda environment with cache redirection
ENV LAMBDA_TASK_ROOT=/var/task
ENV PYTHONPATH="/var/task"
ENV HOME="/tmp"
ENV XDG_CACHE_HOME="/tmp/.cache"
ENV XDG_DATA_HOME="/tmp/.local/share"
ENV XDG_CONFIG_HOME="/tmp/.config"
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy function code to the correct location
COPY index.py ${LAMBDA_TASK_ROOT}/index.py

# Set the Lambda runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["index.lambda_handler"]
