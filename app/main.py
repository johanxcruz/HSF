"""Orquestador: Hardware/FW -> TCP -> SO -> Python -> CSV/Reporte -> Usuario (RF01-RF10)."""
import argparse
import logging
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app import logic, os_info, report
from app.acquisition import Acquirer, FrameTooLarge
from app.persistence import CsvStore
from app.validation import ValidationError, parse_frame


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 5000
    max_messages: int = 100
    max_seconds: float = 60.0
    out_dir: Path = Path("runs/latest")
    read_timeout: float = 1.0
    backoff_start: float = 0.2
    backoff_max: float = 2.0
    status_every: float = 2.0
    quiet: bool = False


def setup_logging(path: Path) -> logging.Logger:
    log = logging.getLogger(f"hsf.{path}")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    log.propagate = False
    h = logging.FileHandler(path, mode="w", encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | evento=%(event)s | resultado=%(result)s | %(message)s"))
    log.addHandler(h)
    return log


def run(cfg: Config, stop: threading.Event = None) -> dict:
    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = setup_logging(out / "events.log")

    def ev(level, event, result, msg=""):
        log.log(level, msg, extra={"event": event, "result": result})

    store, acq, m = CsvStore(out / "data.csv"), Acquirer(cfg.host, cfg.port, cfg.read_timeout), report.Metrics()
    snap, next_os, next_status = os_info.snapshot(out), 0.0, 0.0
    state, last_state, lost_since, consec_to, backoff = "DESCONECTADO", None, None, 0, cfg.backoff_start
    t0 = time.time()
    ev(logging.INFO, "INICIO", "OK", f"destino={cfg.host}:{cfg.port}")

    def status(force=False):
        nonlocal last_state, next_status
        now = time.time()
        if force or state != last_state or now >= next_status:
            last_state, next_status = state, now + cfg.status_every
            if not cfg.quiet:
                print(f"[ESTADO] {state:<13} rx={m.lines:<4} ok={m.valid:<4} rechazadas={sum(m.invalid.values()):<3} "
                      f"anomalias={m.anomalies:<3} cpu={snap.get('cpu_pct')}% mem={snap.get('mem_pct')}%", flush=True)

    def lose(reason):
        nonlocal state, lost_since, consec_to
        acq.close()
        m.connection_errors += 1
        consec_to = 0
        lost_since = lost_since or time.time()
        state = "RECONECTANDO"
        ev(logging.ERROR, "CONEXION_PERDIDA", reason, "se inicia reconexion con backoff")

    while m.lines < cfg.max_messages and time.time() - t0 < cfg.max_seconds and not (stop and stop.is_set()):
        now = time.time()
        if now >= next_os:  # RF06: recursos del SO relacionados con la operacion
            snap, next_os = os_info.snapshot(out), now + 1
            warns = os_info.assess(snap)
            if warns:
                state = "DEGRADADO" if acq.connected else state
                ev(logging.WARNING, "RECURSOS_SO", ",".join(warns), f"cpu={snap['cpu_pct']} mem={snap['mem_pct']}")
        status()

        if not acq.connected:
            try:
                acq.connect()
            except OSError as e:
                m.retries += 1
                state = "RECONECTANDO"
                ev(logging.WARNING, "REINTENTO", "FALLIDO", f"{e.__class__.__name__}; espera={backoff:.1f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, cfg.backoff_max)
                continue
            backoff, state = cfg.backoff_start, "CONECTADO"
            ev(logging.INFO, "CONEXION", "OK", "enlace establecido con el dispositivo")
            continue

        try:
            line = acq.read_line()
            consec_to = 0
        except socket.timeout:
            m.timeouts += 1
            consec_to += 1
            ev(logging.WARNING, "TIMEOUT", f"consecutivos={consec_to}")
            if consec_to >= 2:
                lose("TIMEOUT")
            continue
        except (ConnectionError, OSError) as e:
            lose(e.__class__.__name__)
            continue
        except FrameTooLarge:
            line = None

        t_recv, p0 = time.time(), time.perf_counter()
        m.lines += 1
        try:
            if line is None:
                raise ValidationError("BAD_FORMAT", "buffer excedido")
            frame = parse_frame(line)
        except ValidationError as e:
            m.invalid[e.code] += 1
            if e.frame is None:
                m.unparseable += 1
            else:
                m.note_seq(e.frame.get("seq"))
            ev(logging.WARNING, "TRAMA_RECHAZADA", e.code, e.detail)
            continue

        m.valid += 1
        m.note_seq(frame["seq"])
        estado, motivos = logic.classify(frame)
        if estado == "ANOMALIA":
            m.anomalies += 1
            ev(logging.WARNING, "ANOMALIA", ",".join(motivos), f"{frame['device_id']} seq={frame['seq']} temp={frame['temp_c']}")
        else:
            ev(logging.INFO, "TRAMA_OK", "NORMAL", f"{frame['device_id']} seq={frame['seq']}")
        if lost_since is not None:
            m.recoveries.append(t_recv - lost_since)
            ev(logging.INFO, "RECUPERACION", "OK", f"{t_recv - lost_since:.2f}s desde la deteccion")
            lost_since = None
        if state in ("RECONECTANDO", "DESCONECTADO"):
            state = "CONECTADO"

        lat = (t_recv - frame["ts"]) * 1000
        m.latencies.append(lat)
        ok = store.write({
            "recv_ts": round(t_recv, 3), "device_id": frame["device_id"], "seq": frame["seq"],
            "temp_c": frame["temp_c"], "hum_pct": frame["hum_pct"], "volt_v": frame["volt_v"],
            "estado": estado, "motivos": "|".join(motivos), "latencia_ms": round(lat, 2),
            "proc_ms": round((time.perf_counter() - p0) * 1000, 3),
            "cpu_pct": snap.get("cpu_pct"), "mem_pct": snap.get("mem_pct")})
        if not ok:
            m.storage_errors += 1
            state = "DEGRADADO"
            ev(logging.ERROR, "ALMACENAMIENTO", "FALLO", f"{store.last_error.__class__.__name__}; filas en buffer={len(store.buffer)}")
        m.proc_times.append((time.perf_counter() - p0) * 1000)

    acq.close()
    elapsed = time.time() - t0
    rep = report.build(m, cfg, os_info.snapshot(out), elapsed, store)
    report.write(rep, out)
    state = "FINALIZADO"
    status(force=True)
    ev(logging.INFO, "FIN", "OK", f"recibidas={m.lines} validas={m.valid}")
    return rep


def cli():
    ap = argparse.ArgumentParser(description="Aplicacion HSF: adquisicion de telemetria")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--max-messages", type=int, default=100)
    ap.add_argument("--max-seconds", type=float, default=60)
    ap.add_argument("--out-dir", default="runs/latest")
    a = ap.parse_args()
    run(Config(host=a.host, port=a.port, max_messages=a.max_messages, max_seconds=a.max_seconds, out_dir=Path(a.out_dir)))


if __name__ == "__main__":
    cli()
