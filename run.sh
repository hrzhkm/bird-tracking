#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Configuration file not found: ${ENV_FILE}" >&2
    echo "Copy .env.example to .env and update it for this computer." >&2
    exit 1
fi

# Export every value in .env for both this launcher and the Python process.
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

MODEL_SLOT=""
case "${1:-}" in
    --candidate-safe)
        MODEL_SLOT="candidate"
        export SERVO_ENABLED=0
        shift
        ;;
    --candidate)
        MODEL_SLOT="candidate"
        export SERVO_ENABLED=1
        shift
        ;;
esac

if [[ -z "${MODEL_SLOT}" && -f "${SCRIPT_DIR}/models/production/model.hef" ]]; then
    MODEL_SLOT="production"
fi

if [[ -n "${MODEL_SLOT}" ]]; then
    MODEL_DIR="${SCRIPT_DIR}/models/${MODEL_SLOT}"
    if [[ ! -f "${MODEL_DIR}/model.hef" || ! -f "${MODEL_DIR}/labels.json" ]]; then
        echo "Incomplete ${MODEL_SLOT} model release: ${MODEL_DIR}" >&2
        exit 1
    fi
    export MODEL_HEF_PATH="${MODEL_DIR}/model.hef"
    export MODEL_LABELS_JSON="${MODEL_DIR}/labels.json"
    export MODEL_VERSION="${MODEL_SLOT} · $(basename "$(readlink -f "${MODEL_DIR}")")"
    set -- --hef-path "${MODEL_HEF_PATH}" --labels-json "${MODEL_LABELS_JSON}" "$@"
fi

HAILO_EXAMPLES_DIR="${SCRIPT_DIR}/../hailo-rpi5-examples"

if [[ ! -d "${HAILO_EXAMPLES_DIR}" ]]; then
    echo "Hailo examples directory not found: ${HAILO_EXAMPLES_DIR}" >&2
    exit 1
fi

HAILO_EXAMPLES_DIR="$(cd -- "${HAILO_EXAMPLES_DIR}" && pwd)"
PYTHON_BIN="${HAILO_EXAMPLES_DIR}/venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python environment not found: ${PYTHON_BIN}" >&2
    exit 1
fi

export HAILO_EXAMPLES_DIR
export PYTHONPATH="${HAILO_EXAMPLES_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

# Fail clearly instead of silently running with a missing or wrong accelerator.
if ! command -v hailortcli >/dev/null 2>&1; then
    echo "hailortcli not found; HailoRT is required for accelerated inference." >&2
    exit 1
fi

HAILO_SCAN="$(hailortcli scan 2>&1)"
if ! grep -q "Device:" <<<"${HAILO_SCAN}"; then
    echo "No Hailo accelerator detected; refusing to start CPU-only tracking." >&2
    echo "${HAILO_SCAN}" >&2
    exit 1
fi

# The installed board reports HAILO8 (26 TOPS). Catch an accidental HAILO8L
# resource selection before GStreamer starts with an incompatible HEF.
HAILO_ID="$(hailortcli fw-control identify 2>&1 | tr -d '\000')"
HAILO_DEVICE_ARCH="$(sed -n 's/^Device Architecture: //p' <<<"${HAILO_ID}" | head -n 1)"
EXPECTED_ARCH="${hailo_arch^^}"
if [[ -n "${EXPECTED_ARCH}" && -n "${HAILO_DEVICE_ARCH}" && "${EXPECTED_ARCH}" != "${HAILO_DEVICE_ARCH}" ]]; then
    echo "Hailo architecture mismatch: .env selects ${EXPECTED_ARCH}, device is ${HAILO_DEVICE_ARCH}." >&2
    exit 1
fi

echo "[HAILO] ${HAILO_DEVICE_ARCH:-accelerator detected}; inference will run on ${HAILO_SCAN#*Device: }"

cd "${SCRIPT_DIR}"
exec "${PYTHON_BIN}" -m bird_tracker "$@"
