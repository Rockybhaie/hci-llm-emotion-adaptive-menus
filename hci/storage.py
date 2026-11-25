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
EMOTION_CLASSES = ["anger", "contempt", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
SNAPSHOT = ["samples", "face_fraction", "negative_fraction", "valence", "arousal", "dominant",
            *[f"p_{c}" for c in EMOTION_CLASSES]]

SCHEMAS = {
    "markers": ["t", "step", "step_type", "phase", "query_id", "event"],
    "events": ["t", "step", "query_id", "look", "source", "event", "item", "x", "y", "detail"],
    "mouse": ["t", "x", "y"],
    "aoi": ["t", "snapshot", "kind", "id", "x0", "y0", "x1", "y1"],
    "looks": ["t", "query_id", "look", "reason", "adaptation_id"],
    "questionnaires": ["t", "tag", "query_id", "instrument", "item", "value"],
    # one row per query: the 45-row dataset of the first run
    "interactions": ["participant", "position", "query_id", "query_type", "attempt", "start_look", "looks_seen",
                     "final_look", "n_looks", "n_auto", "n_manual", "n_kept", "n_back", "t_answer", "t_done",
                     "reading_s", "time_per_look", "satisfaction", "preferred_look", "quiz_answer", "quiz_correct",
                     "emotion_samples", "face_fraction", "valence", "arousal", "dominant_emotion",
                     "negative_fraction", "valence_per_look", "dominant_per_look"],
    # one row per look change: emotion before -> change -> reaction -> the query's outcome
    "adaptations": ["participant", "query_id", "query_type", "attempt", "adaptation_id", "t", "trigger",
                    "from_look", "to_look", "n_auto_before", "response", "response_t", "response_s",
                    "time_on_new_look_s", "final_look", "satisfaction", "preferred_look", "quiz_correct",
                    *[f"before_{k}" for k in SNAPSHOT]],
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
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(self.folder / f"{name}.json")

    def read_json(self, name):
        path = self.folder / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def close(self):
        with self._lock:
            for s in self._streams.values():
                s.close()
