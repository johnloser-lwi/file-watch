#!/usr/bin/env bash
# Build the FileWatch GUI as a macOS .app bundle, and optionally install it.
#
#   ./build-gui.sh            # build bin/mac/FileWatch.app
#   ./build-gui.sh --install  # build, then copy to /Applications
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="FileWatch"
OUTPUT_DIR="bin/mac"
ENTRY="src/file_watch/gui/app.py"
VENV="venv"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "[ERROR] build-gui.sh builds a macOS .app; run it on a Mac."
    exit 1
fi

if [[ ! -x "${VENV}/bin/python" ]]; then
    echo "[build] Creating virtual environment in ${VENV}/..."
    python3 -m venv "${VENV}"
fi
PY="${VENV}/bin/python"

if ! "${PY}" -c "import tkinter" 2>/dev/null; then
    echo "[ERROR] This Python has no tkinter. With Homebrew: brew install python-tk"
    exit 1
fi

echo "[build] Installing project and build dependencies..."
"${PY}" -m pip install -q -e . pyinstaller

echo "[build] Cleaning previous GUI build artifacts..."
rm -rf "build/${APP_NAME}" "build/${APP_NAME}.spec" "${OUTPUT_DIR}/${APP_NAME}" "${OUTPUT_DIR}/${APP_NAME}.app"

echo "[build] Building ${APP_NAME}.app..."
"${PY}" -m PyInstaller \
    --windowed \
    --name "${APP_NAME}" \
    --osx-bundle-identifier "com.filewatch.gui" \
    --collect-all ttkbootstrap \
    --paths src \
    --distpath "${OUTPUT_DIR}" \
    --workpath build \
    --specpath build \
    --clean \
    --noconfirm \
    "${ENTRY}"

# --windowed also leaves a bare onedir folder next to the .app; it isn't needed.
rm -rf "${OUTPUT_DIR}/${APP_NAME}"

echo "[build] Built ${OUTPUT_DIR}/${APP_NAME}.app"

if [[ "${1:-}" == "--install" ]]; then
    echo "[install] Copying to /Applications..."
    rm -rf "/Applications/${APP_NAME}.app"
    cp -R "${OUTPUT_DIR}/${APP_NAME}.app" /Applications/
    echo "[install] Installed /Applications/${APP_NAME}.app"
fi
