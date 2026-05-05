#!/usr/bin/env bash
# Build a deterministic Lambda deployment zip containing the gateway source
# plus pinned runtime dependencies. Intended to be invoked by Terraform via
# null_resource; safe to run standalone.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SRC_DIR="${REPO_ROOT}/services/gateway/src"
REQ_FILE="${REPO_ROOT}/services/gateway/requirements.txt"
BUILD_DIR="${REPO_ROOT}/services/gateway/build/lambda-package"

echo "==> Building Lambda package at ${BUILD_DIR}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Pin to manylinux2014_x86_64 wheels for Lambda (python3.12, x86_64 runtime).
python3 -m pip install \
    --quiet \
    --upgrade \
    --target "${BUILD_DIR}" \
    --implementation cp \
    --python-version 3.12 \
    --only-binary=:all: \
    --platform manylinux2014_x86_64 \
    -r "${REQ_FILE}"

# Copy source on top of deps.
cp -R "${SRC_DIR}/gateway" "${BUILD_DIR}/gateway"

# Strip __pycache__ and *.dist-info metadata bloat.
find "${BUILD_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "${BUILD_DIR}" -type d -name "tests" -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> Package contents:"
du -sh "${BUILD_DIR}"
