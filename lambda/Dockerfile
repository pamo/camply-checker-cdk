# Use the official camply Docker image with explicit AMD64 platform
FROM --platform=linux/amd64 juftin/camply:latest

# Install AWS Lambda Runtime Interface Client and additional dependencies
COPY requirements.txt /tmp/
RUN pip install awslambdaric && \
    pip install -r /tmp/requirements.txt

# Set Lambda environment
ENV LAMBDA_TASK_ROOT=/var/task
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy function code
COPY index.py ${LAMBDA_TASK_ROOT}/
COPY camply_filesystem_patch.py ${LAMBDA_TASK_ROOT}/

# Set the Lambda runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["index.lambda_handler"]
