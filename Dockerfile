# Backend for the AI Football Scout — deployed as a Hugging Face Space (Docker SDK).
# HF serves the container on port 7860, so uvicorn must listen there.
FROM python:3.12-slim

# libgomp1 is the OpenMP runtime that lightgbm + torch link against at import time.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces run the container as uid 1000 — match it and give the user a writable HOME
# (torch / langchain may write caches under ~/.cache).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# Install CPU-only PyTorch FIRST so the later `-r requirements.txt` sees torch as already
# satisfied and never pulls the multi-hundred-MB CUDA wheels.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# App code + the runtime artifacts ScoutEngine loads at startup.
COPY --chown=user src ./src
COPY --chown=user data/processed ./data/processed
COPY --chown=user models ./models

EXPOSE 7860
CMD ["uvicorn", "src.scout.api:app", "--host", "0.0.0.0", "--port", "7860"]
