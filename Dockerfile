FROM python:3.12-slim

# Install git and ca-certificates for repository analysis
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Configure git to allow working in volume-mounted directories with arbitrary UID/GID
RUN git config --system --add safe.directory '*'

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY review_app/ /app/review_app/
COPY review.py /app/review.py
COPY .checklist /app/.checklist

# Default repository directory mounted from host
ENV REPO_PATH=/repo
WORKDIR /repo

ENTRYPOINT ["python", "/app/review.py"]
