"""
common.prometheus_multiproc
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Housekeeping for prometheus_client's multiprocess mode under gunicorn.

In multiprocess mode every worker writes its metrics to ``<type>_<pid>.db``
files in ``PROMETHEUS_MULTIPROC_DIR``. prometheus_client never removes a dead
worker's counter/histogram files, so with ``max_requests`` recycling the
directory (a tmpfs under /dev/shm) gains files for every recycled worker and
every scrape reads more of them. ``compact_dead_process`` folds a dead
worker's values into one ``<type>_archive.db`` file per type and deletes its
files, so the file count stays bounded by the number of live workers.

prometheus_client's collector raises ``FileNotFoundError`` if a counter or
histogram file disappears between its directory listing and its read, and a
scrape that read the archive after a merge but the worker file before its
removal would double-count. Compaction therefore holds an exclusive lock and
``/metrics`` collection holds a shared one (``collection_lock``).

Imports nothing from Django: the gunicorn master uses it before any app code
is loaded.
"""

from __future__ import annotations

import fcntl
import glob
import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress

# Types whose values from a dead process stay meaningful and add up.
_ADDITIVE_TYPES = ("counter", "histogram", "summary")
# Every file prefix prometheus_client itself writes.
_METRIC_FILE_TYPES = frozenset({"counter", "gauge", "histogram", "summary"})
_ARCHIVE_ID = "archive"
_LOCK_NAME = ".compaction.lock"


def multiproc_dir() -> str | None:
    """The active multiprocess directory, or None outside multiprocess mode."""
    return os.environ.get("PROMETHEUS_MULTIPROC_DIR") or None


@contextmanager
def _flock(path: str, operation: int) -> Iterator[None]:
    """Hold an flock on the directory's lock file for the duration."""
    fd = os.open(os.path.join(path, _LOCK_NAME), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, operation)
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the lock


@contextmanager
def collection_lock(path: str | None = None) -> Iterator[None]:
    """Shared lock for reading metrics; a no-op outside multiprocess mode."""
    path = path or multiproc_dir()
    if not path:
        yield
        return
    with _flock(path, fcntl.LOCK_SH):
        yield


def _is_metric_file(filename: str) -> bool:
    """Whether ``filename`` is one of prometheus_client's own ``*.db`` files."""
    name = os.path.basename(filename)
    return name.endswith(".db") and name.split("_", 1)[0] in _METRIC_FILE_TYPES


def compact_dead_process(pid: int, path: str | None = None) -> None:
    """Fold a dead worker's metric files into the archive files and delete them.

    Counters, histograms and summaries are summed into ``<type>_archive.db``
    so totals never drop. ``all``-mode gauge files are deleted (a dead
    process's gauge reading is stale), and live-mode gauges are handled by
    prometheus_client's own ``mark_process_dead``.
    """
    from prometheus_client import multiprocess
    from prometheus_client.mmap_dict import MmapedDict

    path = path or multiproc_dir()
    if not path:
        return
    with _flock(path, fcntl.LOCK_EX):
        for typ in _ADDITIVE_TYPES:
            src = os.path.join(path, f"{typ}_{pid}.db")
            if not os.path.exists(src):
                continue
            archive = MmapedDict(os.path.join(path, f"{typ}_{_ARCHIVE_ID}.db"))
            try:
                for key, value, timestamp, _pos in MmapedDict.read_all_values_from_file(
                    src
                ):
                    current, _ = archive.read_value(key)
                    archive.write_value(key, current + value, timestamp)
            finally:
                archive.close()
            os.remove(src)
        for f in glob.glob(os.path.join(path, f"gauge_all_{pid}.db")):
            os.remove(f)
        multiprocess.mark_process_dead(pid, path)


def clear_metric_files(path: str) -> None:
    """Delete prometheus_client's ``*.db`` files in ``path`` and nothing else."""
    if not os.path.isdir(path):
        return
    with _flock(path, fcntl.LOCK_EX):
        for f in glob.glob(os.path.join(path, "*.db")):
            if _is_metric_file(f):
                os.remove(f)


def remove_multiproc_dir(path: str) -> None:
    """Clear ``path``'s metric files, then remove it if nothing else is left."""
    clear_metric_files(path)
    with suppress(OSError):
        os.remove(os.path.join(path, _LOCK_NAME))
        os.rmdir(path)  # fails, and is skipped, if anything unrelated remains
