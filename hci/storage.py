"""Crash-safe CSV/JSON writers for one participant's session folder."""

import csv
import json
import threading
import time
from pathlib import Path


class CsvStream:
    """Append-only CSV. Low-rate streams flush every row; high-rate ones every `flush_s`."""

    def __init__(self, path: Path, columns, flush_s=0.0):
        self.path = path
        self.columns = list(columns)
        self.flush_s = flush_s
        self.rows = 0
        self._lock = threading.Lock()
        is_new = not path.exists() or path.stat().st_size == 0
        self._file = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if is_new:
            self._writer.writerow(self.columns)
            self._file.flush()
        self._last_flush = time.monotonic()

    def write(self, row):
        if isinstance(row, dict):
            row = [row.get(c, "") for c in self.columns]
        with self._lock:
            if self._file.closed:
                return
            self._writer.writerow(row)
            self.rows += 1
            now = time.monotonic()
            if now - self._last_flush >= self.flush_s:
                self._file.flush()
                self._last_flush = now

    def close(self):
        with self._lock:
            if not self._file.closed:
                self._file.flush()
                self._file.close()


# Columns of every behavioural file written by the session (sensor files are defined by each adapter).
SCHEMAS = {
    "markers": ["t", "step", "step_type", "phase", "block", "emotion", "event"],
    "events": ["t", "step", "block", "task_id", "source", "event", "section", "page", "item", "x", "y", "detail"],
    "mouse": ["t", "x", "y"],
    "aoi": ["t", "snapshot", "kind", "id", "x0", "y0", "x1", "y1"],
    "tasks": ["block", "emotion", "task_set", "variant", "task_id", "type", "target_pages",
              "t_start", "t_end", "duration_s", "outcome", "answer", "correct_answer",
              "clicks", "menu_opens", "page_views", "wrong_pages", "sabotage_events", "answer_attempts"],
    "questionnaires": ["t", "tag", "block", "emotion", "instrument", "item", "value"],
}


class SessionStore:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self._streams = {}
        self._lock = threading.Lock()

    def stream(self, name, columns=None, flush_s=0.0):
        with self._lock:
            if name not in self._streams:
                cols = columns or SCHEMAS[name]
                self._streams[name] = CsvStream(self.folder / f"{name}.csv", cols, flush_s)
            return self._streams[name]

    def write(self, name, row):
        self.stream(name).write(row)

    def write_json(self, name, data):
        tmp = self.folder / f".{name}.json.tmp"
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.folder / f"{name}.json")

    def read_json(self, name):
        path = self.folder / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def close(self):
        with self._lock:
            for s in self._streams.values():
                s.close()
