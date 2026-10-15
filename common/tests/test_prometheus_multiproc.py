"""
Tests for common.prometheus_multiproc.

Covers:
- compact_dead_process: totals are unchanged, the dead worker's files are gone
- compact_dead_process: repeated compactions keep accumulating into the archive
- compact_dead_process: "all"-mode gauge files of the dead worker are removed
- clear_metric_files: only prometheus_client's own *.db files are deleted
- remove_multiproc_dir: keeps a directory that still holds unrelated files
- collection_lock: blocks compaction while a scrape is reading
"""

from __future__ import annotations

import os
import tempfile
import threading
import time

from django.test import SimpleTestCase
from prometheus_client import CollectorRegistry
from prometheus_client.mmap_dict import MmapedDict, mmap_key
from prometheus_client.multiprocess import MultiProcessCollector

from common.prometheus_multiproc import (
    clear_metric_files,
    collection_lock,
    compact_dead_process,
    remove_multiproc_dir,
)


def _write(path, filename, metric, value, labels=None):
    """Write one sample into a prometheus_client multiprocess file."""
    labels = labels or {}
    d = MmapedDict(os.path.join(path, filename))
    try:
        key = mmap_key(metric, metric, list(labels), list(labels.values()), "help")
        current, _ = d.read_value(key)
        d.write_value(key, current + value, 0.0)
    finally:
        d.close()


def _scrape(path):
    """Return {(sample name, labels tuple): value} as /metrics would report."""
    registry = CollectorRegistry()
    MultiProcessCollector(registry, path)
    return {
        (s.name, tuple(sorted(s.labels.items()))): s.value
        for metric in registry.collect()
        for s in metric.samples
    }


class CompactDeadProcessTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_totals_unchanged_and_dead_files_removed(self):
        _write(self.path, "counter_100.db", "reqs_total", 3)
        _write(self.path, "counter_200.db", "reqs_total", 4)
        _write(self.path, "histogram_100.db", "lat_sum", 1.5)
        before = _scrape(self.path)

        compact_dead_process(100, self.path)

        self.assertEqual(_scrape(self.path), before)
        self.assertFalse(os.path.exists(os.path.join(self.path, "counter_100.db")))
        self.assertFalse(os.path.exists(os.path.join(self.path, "histogram_100.db")))
        self.assertTrue(os.path.exists(os.path.join(self.path, "counter_200.db")))

    def test_successive_compactions_accumulate(self):
        for pid in (1, 2, 3):
            _write(self.path, f"counter_{pid}.db", "reqs_total", 10, {"s": "200"})
            compact_dead_process(pid, self.path)

        self.assertEqual(
            sorted(os.listdir(self.path)), [".compaction.lock", "counter_archive.db"]
        )
        self.assertEqual(_scrape(self.path)[("reqs_total", (("s", "200"),))], 30)

    def test_all_mode_gauge_of_dead_worker_is_removed(self):
        _write(self.path, "gauge_all_100.db", "temp", 5)
        compact_dead_process(100, self.path)
        self.assertFalse(os.path.exists(os.path.join(self.path, "gauge_all_100.db")))


class ClearMetricFilesTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_only_metric_files_are_deleted(self):
        _write(self.path, "counter_1.db", "reqs_total", 1)
        _write(self.path, "gauge_livesum_1.db", "g", 1)
        for unrelated in ("notes.txt", "app.db", "important_data.db"):
            with open(os.path.join(self.path, unrelated), "w") as f:
                f.write("keep me")

        clear_metric_files(self.path)

        self.assertEqual(
            sorted(os.listdir(self.path)),
            [".compaction.lock", "app.db", "important_data.db", "notes.txt"],
        )

    def test_remove_dir_keeps_directory_with_unrelated_files(self):
        _write(self.path, "counter_1.db", "reqs_total", 1)
        with open(os.path.join(self.path, "notes.txt"), "w") as f:
            f.write("keep me")

        remove_multiproc_dir(self.path)

        self.assertEqual(os.listdir(self.path), ["notes.txt"])

    def test_remove_dir_removes_empty_directory(self):
        sub = os.path.join(self.path, "gunicorn-1")
        os.mkdir(sub)
        _write(sub, "counter_1.db", "reqs_total", 1)

        remove_multiproc_dir(sub)

        self.assertFalse(os.path.exists(sub))


class CollectionLockTests(SimpleTestCase):
    def test_compaction_waits_for_an_active_scrape(self):
        with tempfile.TemporaryDirectory() as path:
            _write(path, "counter_7.db", "reqs_total", 1)
            done = threading.Event()

            def _compact():
                compact_dead_process(7, path)
                done.set()

            with collection_lock(path):
                worker = threading.Thread(target=_compact)
                worker.start()
                time.sleep(0.2)
                self.assertFalse(done.is_set())
                self.assertTrue(os.path.exists(os.path.join(path, "counter_7.db")))

            worker.join(timeout=5)
            self.assertTrue(done.is_set())

    def test_no_op_outside_multiprocess_mode(self):
        env = os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
        try:
            with collection_lock():
                pass
        finally:
            if env is not None:
                os.environ["PROMETHEUS_MULTIPROC_DIR"] = env
