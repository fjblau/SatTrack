FROM python:3.11-slim

ARG GITHUB_TOKEN

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgtk2.0-0 \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/octet-stream" \
    "https://api.github.com/repos/fjblau/gmat-binaries/releases/assets/402371855" \
    -o /tmp/gmat.tar.gz \
    && mkdir -p /opt/gmat \
    && tar -xzf /tmp/gmat.tar.gz -C /opt/gmat --strip-components=1 \
    && rm /tmp/gmat.tar.gz

ENV GMAT_HOME=/opt/gmat

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "start.py"]
