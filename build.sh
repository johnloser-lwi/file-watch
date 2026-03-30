#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="bin/mac"
ENTRY="src/file_watch/__main__.py"
APP_NAME="file-watch"

echo "[build] Checking PyInstaller..."
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo "[build] Installing PyInstaller..."
    pip install pyinstaller -q || { echo "[ERROR] Failed to install PyInstaller."; exit 1; }
fi

echo "[build] Cleaning previous build artifacts..."
rm -rf build dist "${APP_NAME}.spec"

echo "[build] Building executable..."
pyinstaller \
    --onefile \
    --name "${APP_NAME}" \
    --distpath "${OUTPUT_DIR}" \
    --workpath build \
    --specpath build \
    --clean \
    --noconfirm \
    "${ENTRY}"

if [ $? -ne 0 ]; then
    echo "[ERROR] PyInstaller failed."
    exit 1
fi

echo ""
echo "[build] Done."
echo "[build] Executable: ${OUTPUT_DIR}/${APP_NAME}"
echo "[build] Size:"
if [[ "$(uname)" == "Darwin" ]]; then
    stat -f "        %z bytes" "${OUTPUT_DIR}/${APP_NAME}"
else
    stat --printf="        %s bytes\n" "${OUTPUT_DIR}/${APP_NAME}"
fi
