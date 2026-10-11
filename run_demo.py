"""Genera la evidencia para el video: corrida base y corrida con fallos controlados."""
import json
import threading
import time
from pathlib import Path

from app.main import Config, run
from firmware_sim.device_sim import DeviceSimulator


def escenario(nombre, n, outage=False, **sim_kw):
    out = Path("evidence") / nombre
    sim = DeviceSimulator(interval=0.05, **sim_kw)
    sim.start()
    if outage:
        def caida():
            time.sleep(2.0); sim.stop(); time.sleep(1.5); sim.start()
        threading.Thread(target=caida, daemon=True).start()
    print(f"\n=== Escenario: {nombre} ===")
    rep = run(Config(port=sim.port, max_messages=n, max_seconds=60, out_dir=out, read_timeout=1.0))
    sim.stop()
    return rep


if __name__ == "__main__":
    a = escenario("baseline", 120, anomaly_every=20)
    b = escenario("fallos", 160, outage=True, anomaly_every=20, corrupt_every=17, badjson_every=29, badrange_every=41)
    Path("evidence/summary.json").write_text(json.dumps({"baseline": a, "fallos": b}, indent=2, ensure_ascii=False))
    for k, r in (("baseline", a), ("fallos", b)):
        print(f"\n{k}: ", {i: (v["valor"], "OK" if v["cumple"] else "NO") for i, v in r["indicadores"].items()})
