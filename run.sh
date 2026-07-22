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

HAILO_EXAMPLES_DIR="${HAILO_EXAMPLES_DIR:-../hailo-rpi5-examples}"
if [[ "${HAILO_EXAMPLES_DIR}" != /* ]]; then
    HAILO_EXAMPLES_DIR="${SCRIPT_DIR}/${HAILO_EXAMPLES_DIR}"
fi

if [[ ! -d "${HAILO_EXAMPLES_DIR}" ]]; then
    echo "Hailo examples directory not found: ${HAILO_EXAMPLES_DIR}" >&2
    echo "Set HAILO_EXAMPLES_DIR to its location and try again." >&2
    exit 1
fi

HAILO_EXAMPLES_DIR="$(cd -- "${HAILO_EXAMPLES_DIR}" && pwd)"
PYTHON_BIN="${BIRD_TRACKER_PYTHON:-${HAILO_EXAMPLES_DIR}/venv/bin/python}"
if [[ "${PYTHON_BIN}" != /* ]]; then
    PYTHON_BIN="${SCRIPT_DIR}/${PYTHON_BIN}"
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Python environment not found: ${PYTHON_BIN}" >&2
    echo "Set BIRD_TRACKER_PYTHON to a Python executable with the Hailo dependencies." >&2
    exit 1
fi

export HAILO_EXAMPLES_DIR
export PYTHONPATH="${HAILO_EXAMPLES_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

cd "${SCRIPT_DIR}"
exec "${PYTHON_BIN}" -m bird_tracker "$@"
