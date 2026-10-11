"""Persistencia en CSV con buffer en memoria ante fallos de escritura (RF07, RF09)."""
import csv
from collections import deque
from pathlib import Path

FIELDS = ["recv_ts", "device_id", "seq", "temp_c", "hum_pct", "volt_v", "estado", "motivos",
          "latencia_ms", "proc_ms", "cpu_pct", "mem_pct"]


class CsvStore:
    def __init__(self, path, max_buffer=1000):
        self.path = Path(path)
        self.buffer = deque()
        self.max_buffer = max_buffer
        self.errors = 0
        self.dropped = 0
        self.last_error = None

    def write(self, row: dict) -> bool:
        if len(self.buffer) >= self.max_buffer:
            self.buffer.popleft()
            self.dropped += 1
        self.buffer.append(row)
        try:
            self._flush()
            return True
        except OSError as e:  # PermissionError, ruta inaccesible, disco lleno...
            self.errors += 1
            self.last_error = e
            return False

    def _flush(self):
        new = not self.path.exists() or self.path.stat().st_size == 0
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, FIELDS)
            if new:
                w.writeheader()
            while self.buffer:
                w.writerow(self.buffer[0])
                self.buffer.popleft()
