"""Create a consistent SQLite snapshot; never overwrite a destination or source."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def snapshot(source: Path, destination: Path) -> None:
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file() or source == destination:
        raise ValueError("Source must be an existing database, distinct from destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reserve exclusively: an existing backup/live database is never replaced.
    with destination.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30)) as src:
            with closing(sqlite3.connect(destination.as_uri() + "?mode=rw", uri=True)) as dst:
                src.backup(dst, pages=256, sleep=0.1)
                if dst.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise RuntimeError("Backup integrity check failed")
    except Exception:
        # Only remove the newly reserved, incomplete output from this invocation.
        destination.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, help="New path only; also used to rehearse restore without touching live data")
    args = parser.parse_args()
    snapshot(args.source, args.destination)
    print("SQLite snapshot created; integrity_check=ok")
