"""Simulador de firmware: dispositivo ambiental ENV-001 que emite telemetria por TCP.

Protocolo: una trama JSON por linea (UTF-8, terminada en \\n) con CRC32 del payload.
Incluye inyeccion de anomalias fisicas y de fallos de comunicacion para las pruebas.
"""
import argparse
import json
import random
import socket
import threading
import time
import zlib


def crc_of(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"{zlib.crc32(raw):08x}"


def build_frame(device_id, seq, temp, hum, volt, ts=None) -> dict:
    payload = {
        "device_id": device_id,
        "seq": seq,
        "ts": time.time() if ts is None else ts,
        "temp_c": round(temp, 2),
        "hum_pct": round(hum, 2),
        "volt_v": round(volt, 3),
    }
    payload["crc"] = crc_of(payload)
    return payload


class DeviceSimulator:
    KINDS = ("anomaly", "corrupt", "badjson", "badrange")

    def __init__(self, host="127.0.0.1", port=0, device_id="ENV-001", interval=0.1,
                 anomaly_every=0, corrupt_every=0, badjson_every=0, badrange_every=0, seed=7):
        self.host, self.port, self.device_id, self.interval = host, port, device_id, interval
        self.every = {"anomaly": anomaly_every, "corrupt": corrupt_every,
                      "badjson": badjson_every, "badrange": badrange_every}
        self.pending = {k: 0 for k in self.KINDS}
        self.seq = 0
        self.rng = random.Random(seed)
        self._stop = threading.Event()
        self._thread = None
        self._srv = None
        self._stopped_at = None

    # -- control --------------------------------------------------------
    def inject(self, kind: str, count: int = 1):
        self.pending[kind] += count

    def start(self):
        if self._stopped_at is not None:  # el sensor siguio muestreando durante la caida
            self.seq += int((time.time() - self._stopped_at) / self.interval)
            self._stopped_at = None
        self._stop.clear()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        self.port = srv.getsockname()[1]
        srv.listen(1)
        srv.settimeout(0.2)
        self._srv = srv
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._stopped_at = time.time()

    # -- internals ------------------------------------------------------
    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._stream(conn)
        self._srv.close()

    def _stream(self, conn):
        with conn:
            while not self._stop.is_set():
                try:
                    conn.sendall(self._next_line())
                except OSError:
                    return
                time.sleep(self.interval)

    def _kind_for(self, seq):
        for k in self.KINDS:
            if self.pending[k] > 0:
                self.pending[k] -= 1
                return k
        for k in self.KINDS:
            if self.every[k] and seq % self.every[k] == 0:
                return k
        return None

    def _next_line(self) -> bytes:
        self.seq += 1
        kind = self._kind_for(self.seq)
        r = self.rng
        temp, hum, volt = r.gauss(24, 1.2), r.gauss(55, 4), r.gauss(3.7, 0.04)
        if kind == "anomaly":
            temp = r.uniform(38, 45)
        if kind == "badrange":
            temp = 999.0
        if kind == "badjson":
            return b"{esto-no-es-json\n"
        frame = build_frame(self.device_id, self.seq, temp, hum, volt)
        if kind == "corrupt":
            frame["temp_c"] = round(frame["temp_c"] + 5, 2)  # CRC ya no coincide
        return (json.dumps(frame) + "\n").encode()


def main():
    ap = argparse.ArgumentParser(description="Simulador de firmware ENV-001")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--interval", type=float, default=0.1)
    ap.add_argument("--anomaly-every", type=int, default=0)
    ap.add_argument("--corrupt-every", type=int, default=0)
    ap.add_argument("--badjson-every", type=int, default=0)
    a = ap.parse_args()
    sim = DeviceSimulator(port=a.port, interval=a.interval, anomaly_every=a.anomaly_every,
                          corrupt_every=a.corrupt_every, badjson_every=a.badjson_every)
    sim.start()
    print(f"[FW-SIM] {sim.device_id} escuchando en {sim.host}:{sim.port} (Ctrl+C para salir)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sim.stop()


if __name__ == "__main__":
    main()
