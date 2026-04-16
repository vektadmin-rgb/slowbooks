"""
file_watcher.py — Slowbooks
Watches ~/Downloads for new project files (.py, .db, .csv, .json)
and moves them into the Slowbooks folder alongside this script.

Run:  python file_watcher.py
      python file_watcher.py --once     # dry-run: show what would move, then exit
Stop: Ctrl+C

No external dependencies — uses stdlib polling.
"""

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DEST_DIR   = Path(__file__).parent                   # same folder as this script
WATCH_DIR  = Path.home() / "Downloads"
POLL_SEC   = 3                                        # check every N seconds
EXTENSIONS = {".py", ".db", ".csv", ".json", ".toml", ".cfg", ".md", ".txt"}

# Files to never touch (guard against moving unrelated downloads)
IGNORE_PREFIXES = ("~", ".")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _is_watched(path: Path) -> bool:
    name = path.name
    return (
        path.is_file()
        and path.suffix.lower() in EXTENSIONS
        and not any(name.startswith(p) for p in IGNORE_PREFIXES)
    )


def _safe_dest(src: Path) -> Path:
    """Return a destination path that won't silently overwrite an existing file."""
    dest = DEST_DIR / src.name
    if not dest.exists():
        return dest
    # Append timestamp to avoid collision
    stem   = src.stem
    suffix = src.suffix
    tag    = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEST_DIR / f"{stem}_{tag}{suffix}"


def move_file(src: Path, dry_run: bool = False) -> Path | None:
    dest = _safe_dest(src)
    if dry_run:
        _log(f"[DRY RUN] would move  {src.name}  →  {dest.name}")
        return dest
    try:
        shutil.move(str(src), str(dest))
        _log(f"MOVED  {src.name}  →  {dest}")
        return dest
    except Exception as e:
        _log(f"ERROR moving {src.name}: {e}")
        return None


# ─────────────────────────────────────────────
# WATCHER
# ─────────────────────────────────────────────
class DownloadWatcher:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._seen: set[Path] = set()

    def _snapshot(self) -> set[Path]:
        try:
            return {p for p in WATCH_DIR.iterdir() if _is_watched(p)}
        except PermissionError:
            return set()

    def run(self):
        if not WATCH_DIR.exists():
            _log(f"Watch directory not found: {WATCH_DIR}")
            sys.exit(1)

        _log(f"Slowbooks file watcher started")
        _log(f"  Watching : {WATCH_DIR}")
        _log(f"  Dest     : {DEST_DIR}")
        _log(f"  Types    : {', '.join(sorted(EXTENSIONS))}")
        _log(f"  Interval : {POLL_SEC}s")
        if self.dry_run:
            _log("  Mode     : DRY RUN — no files will actually move")
        _log("Press Ctrl+C to stop.\n")

        self._seen = self._snapshot()

        while True:
            time.sleep(POLL_SEC)
            current = self._snapshot()
            new_files = current - self._seen

            for path in sorted(new_files):
                # Brief pause so the file finishes writing before we move it
                time.sleep(0.5)
                if path.exists():
                    move_file(path, dry_run=self.dry_run)

            self._seen = current

    def run_once(self):
        """Scan Downloads right now and move anything that matches."""
        _log(f"One-time scan of {WATCH_DIR}")
        found = 0
        for path in sorted(self._snapshot()):
            move_file(path, dry_run=self.dry_run)
            found += 1
        _log(f"Done. {found} file(s) processed.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Move new .py / project files from Downloads into Slowbooks."
    )
    parser.add_argument("--once",    action="store_true",
                        help="Scan once and exit instead of watching continuously.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would move without actually moving anything.")
    args = parser.parse_args()

    watcher = DownloadWatcher(dry_run=args.dry_run)

    if args.once:
        watcher.run_once()
    else:
        try:
            watcher.run()
        except KeyboardInterrupt:
            _log("Watcher stopped.")


if __name__ == "__main__":
    main()
