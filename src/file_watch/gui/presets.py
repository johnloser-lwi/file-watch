"""Centralized filter presets for quick configuration."""

from __future__ import annotations

EXTENSION_PRESETS: dict[str, dict] = {
    "video": {
        "label": "\U0001F3AC Video",
        "extensions": [
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
            ".m4v", ".ts", ".vob",
        ],
    },
    "image": {
        "label": "\U0001F5BC Image",
        "extensions": [
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic",
            ".bmp", ".tiff", ".tif", ".svg", ".ico", ".raw",
        ],
    },
    "document": {
        "label": "\U0001F4C4 Documents",
        "extensions": [
            ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
            ".txt", ".csv", ".rtf", ".odt", ".ods",
        ],
    },
    "audio": {
        "label": "\U0001F3B5 Audio",
        "extensions": [
            ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
            ".wma", ".opus", ".aiff",
        ],
    },
    "archive": {
        "label": "\U0001F4E6 Archives",
        "extensions": [
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
            ".xz", ".iso", ".dmg",
        ],
    },
}

IGNORE_PRESETS: dict[str, dict] = {
    "junk_files": {
        "label": "\U0001F6AB Junk Files",
        "extensions": [".tmp", ".part", ".crdownload", ".download"],
        "patterns": [
            "Thumbs.db", ".DS_Store", "desktop.ini",
            "~*", ".~*", "*.!ut",
        ],
    },
    "common_folders": {
        "label": "\U0001F4C1 Ignore Folders",
        "patterns": [
            "node_modules", ".git", "__pycache__", ".venv",
            ".idea", ".vscode", ".svn",
        ],
    },
}
