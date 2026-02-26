# file-watch

A cross-platform CLI tool that monitors a source folder and automatically moves new files to a destination folder — but only after confirming the file size has been stable for a configurable period. This prevents partially-downloaded or still-being-written files from being moved prematurely.

Supports **type-based routing** (different destinations per file extension) and **ignore rules** (skip files by extension or glob pattern).

---

## Table of Contents

- [Installation](#installation)
  - [From source (Python)](#from-source-python)
  - [Windows executable](#windows-executable)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
  - [Global options](#global-options)
  - [`start`](#start)
  - [`version`](#version)
  - [`config-path`](#config-path)
- [Configuration file](#configuration-file)
  - [Search order](#search-order)
  - [Routes (multiple destinations)](#routes-multiple-destinations)
  - [Ignore rules](#ignore-rules)
  - [All options](#all-options)
- [Conflict resolution](#conflict-resolution)
- [Building the Windows executable](#building-the-windows-executable)
- [Running tests](#running-tests)

---

## Installation

### From source (Python)

Requires Python 3.8 or later.

```bash
pip install -e .
```

For development dependencies (includes pytest):

```bash
pip install -e ".[dev]"
```

### Windows executable

Pre-built executables are not distributed. Build one locally — see [Building the Windows executable](#building-the-windows-executable).

---

## Quick start

```bash
# Simple: watch D:\Downloads, move all stable files to D:\Sorted
file-watch start -s D:\Downloads -d D:\Sorted

# Dry run — see what would be moved without moving anything
file-watch start -s D:\Downloads -d D:\Sorted --dry-run

# Ignore temp/partial files from the command line
file-watch start -s D:\Downloads -d D:\Sorted \
  --ignore-ext .tmp --ignore-ext .part --ignore-pattern "*.crdownload"

# Type-based routing requires a config file (see below)
file-watch --config file-watch.toml start
```

Press `Ctrl+C` to stop.

---

## CLI reference

```
file-watch [--config PATH] [--log-level LEVEL] COMMAND [ARGS]...
```

### Global options

| Flag | Description |
|---|---|
| `--config PATH` | Path to a TOML config file. Overrides the default search order. |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. Overrides the config file value. |
| `--help` | Show help and exit. |

### `start`

Watch a source directory and move stable files to a destination.

```
file-watch start [OPTIONS]
```

| Flag | Default | Description |
|---|---|---|
| `-s, --source PATH` | *(required)* | Directory to watch for new files. |
| `-d, --destination PATH` | *(required unless routes in config)* | Catch-all destination. For type-based routing, define `[[routes]]` in a config file instead. |
| `--stable-for FLOAT` | `5.0` | Seconds a file's size must be unchanged before it is moved. |
| `--poll-interval FLOAT` | `1.0` | How often (in seconds) to check pending file sizes. |
| `--max-wait FLOAT` | `0` | Maximum seconds to track a file that is still growing. `0` means wait forever. |
| `--on-conflict` | `rename` | What to do when the destination file already exists: `skip`, `overwrite`, or `rename`. |
| `--rename-template TEXT` | `{stem}_{n}{suffix}` | Template used when `--on-conflict rename`. |
| `--log-file PATH` | *(stderr only)* | Write log output to this file in addition to stderr. |
| `--dry-run` | off | Log what would be moved without actually moving anything. |
| `--ignore-ext EXT` | *(none)* | Extension to ignore, e.g. `.tmp`. Repeatable. |
| `--ignore-pattern PATTERN` | *(none)* | Glob filename pattern to ignore, e.g. `~*`. Repeatable. |

**Examples:**

```bash
# Basic catch-all destination
file-watch start -s D:\Downloads -d D:\Sorted

# Ignore partial files
file-watch start -s D:\Downloads -d D:\Sorted \
  --ignore-ext .tmp --ignore-ext .part \
  --ignore-pattern "~*" --ignore-pattern "*.crdownload"

# Use a config file for type-based routing
file-watch --config file-watch.toml start

# Combine config file with CLI overrides
file-watch --config file-watch.toml start --stable-for 10 --dry-run
```

### `version`

Print the version and exit.

```bash
file-watch version
# file-watch 0.1.0
```

### `config-path`

Print the resolved config file path and exit. Useful for debugging which config is active.

```bash
file-watch config-path
# C:\Users\you\AppData\Roaming\file-watch\config.toml
```

---

## Configuration file

All CLI flags can be set in a TOML config file. CLI flags always take precedence over the config file.

Copy `config.example.toml` to get started:

```bash
cp config.example.toml file-watch.toml
```

### Search order

The first file found wins:

1. `--config PATH` (explicit CLI flag)
2. `file-watch.toml` in the **current working directory**
3. Platform user config directory:
   - **Windows:** `%APPDATA%\file-watch\config.toml`
   - **macOS:** `~/Library/Application Support/file-watch/config.toml`
   - **Linux:** `$XDG_CONFIG_HOME/file-watch/config.toml` (default: `~/.config/file-watch/config.toml`)

### Routes (multiple destinations)

Define `[[routes]]` sections to send different file types to different folders. Rules are evaluated **top-to-bottom**; the first match wins. A route without an `extensions` list is a **catch-all** and must be placed last.

```toml
[watch]
source = "D:/Downloads"
stable_for = 5.0

[[routes]]
destination = "D:/Sorted/Documents"
extensions = [".pdf", ".docx", ".xlsx", ".txt"]

[[routes]]
destination = "D:/Sorted/Images"
extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

[[routes]]
destination = "D:/Sorted/Video"
extensions = [".mp4", ".mkv", ".avi", ".mov"]

[[routes]]
# No extensions = catch-all for anything not matched above
destination = "D:/Sorted/Other"
```

> **Backward compatibility:** The old single-destination style (`destination = "..."` under `[watch]`) still works and creates an implicit catch-all route.

### Ignore rules

Files matching any ignore rule are silently skipped — they are never tracked, polled, or moved.

```toml
[ignore]
extensions = [".tmp", ".part", ".crdownload", ".download"]
patterns   = ["~*", ".~*", "*.!ut", "desktop.ini", "Thumbs.db"]
```

| Setting | Description |
|---|---|
| `extensions` | File extensions to ignore (case-insensitive, leading dot optional). |
| `patterns` | Glob patterns matched against the **filename only** (not the full path). Uses Python `fnmatch` syntax: `*` matches any characters, `?` matches one character. |

CLI `--ignore-ext` and `--ignore-pattern` values are **added to** (not replaced by) whatever the config file defines.

### All options

```toml
[watch]
source = "D:/Downloads"        # source directory (required)
stable_for = 5.0               # seconds of size stability before moving
poll_interval = 1.0            # how often to check file sizes
max_wait = 0                   # max seconds to track a still-growing file (0 = forever)

[[routes]]
destination = "D:/Sorted/Docs"
extensions = [".pdf", ".docx"]

[[routes]]
destination = "D:/Sorted/Other"   # catch-all (no extensions)

[ignore]
extensions = [".tmp", ".part"]
patterns   = ["~*", "*.crdownload"]

[move]
on_conflict = "rename"                  # skip | overwrite | rename
rename_template = "{stem}_{n}{suffix}"  # must contain {n} or {ts}

[logging]
level = "INFO"                 # DEBUG | INFO | WARNING | ERROR
log_file = ""                  # path to log file; empty = stderr only
log_max_bytes = 10485760       # rotate log file at this size (10 MB)
log_backup_count = 3           # number of rotated log files to keep
```

---

## Conflict resolution

Controlled by `--on-conflict` / `on_conflict` in config:

| Strategy | Behaviour |
|---|---|
| `rename` *(default)* | Appends `_1`, `_2`, … to the stem until a free name is found. Falls back to a Unix timestamp suffix if all numbered slots up to 9999 are taken. |
| `skip` | Leaves the source file in place and logs a message. |
| `overwrite` | Deletes the existing destination file, then moves the source. |

**Rename template tokens** (used when `on_conflict = "rename"`):

| Token | Value |
|---|---|
| `{stem}` | Filename without extension (`report`) |
| `{suffix}` | Extension including dot (`.pdf`) |
| `{n}` | Incrementing integer starting at 1 |
| `{ts}` | Unix timestamp (fallback only) |

The template **must** contain `{n}` or `{ts}`. The default `{stem}_{n}{suffix}` produces `report_1.pdf`, `report_2.pdf`, etc.

---

## Building the Windows executable

Requires Python 3.8+ and an internet connection (to install PyInstaller on first run).

```bat
build.bat
```

The script:
1. Installs PyInstaller if it is not already present.
2. Compiles a single-file executable with no external dependencies.
3. Places the result at `bin\win\file-watch.exe`.

**Using the executable:**

```bat
bin\win\file-watch.exe --help
bin\win\file-watch.exe start -s D:\Downloads -d D:\Sorted --stable-for 5
bin\win\file-watch.exe --config file-watch.toml start
```

The executable is self-contained and does not require Python to be installed on the target machine.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v --timeout=30
```
