# gridcast — the pinned environment (PLANNING 14, step 0a).
#
# Written before any result exists. Retrofitting a pinned environment after
# nine steps of results means none of those nine results are reproducible,
# and nobody goes back to redo them.
#
# This image is one of the five pins: code (git sha), data (DVC hash),
# settings (config/config.yaml, covered by the git sha), environment (this
# image's digest), randomness (train.seed).
#
# Base pinned by digest, not by tag. A tag is a moving pointer; a digest is
# the thing itself.
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

# libgomp1 is LightGBM's OpenMP runtime on Linux. Without it `import lightgbm`
# fails at dlopen, not at pip install — so it must be here, not in requirements.
# git is needed because the daily job commits state/ back (PLANNING 14).
#
# Deliberately not version-pinned. The base image is pinned by digest and the
# Python dependencies are pinned exactly; these two are stable C-level
# libraries whose Debian point releases are security patches. Pinning them
# would mean writing version strings that cannot be verified from here, and an
# unverified pin is a guess wearing a pin's clothing.
RUN apt-get update \
 && apt-get install --no-install-recommends -y libgomp1 git \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MLFLOW_DISABLE_AGENT_HINT=1

WORKDIR /app

# Dependencies first, so a source edit does not invalidate the install layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && python -c "import lightgbm, pandas, dvc, mlflow, optuna"

COPY . .

# Fail loudly if the image cannot even find its own config (PLANNING 5h:
# missing required config key -> fail fast at startup).
RUN python -c "from src.config import load_config; load_config()"

CMD ["pytest", "-q", "tests/"]
