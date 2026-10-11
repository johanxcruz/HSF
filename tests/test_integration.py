"""Matriz de pruebas TP-01 .. TP-09 (ver docs/matriz_pruebas.md)."""
import csv
import threading
import time
from pathlib import Path

from app import logic, os_info
from app.main import Config, run
from app.persistence import CsvStore
from app.validation import ValidationError, parse_frame
from firmware_sim.device_sim import DeviceSimulator, build_frame
import json
import pytest


def run_with_sim(tmp_path, n=30, inject=None, **sim_kw):
    sim = DeviceSimulator(interval=0.01, **sim_kw)
    for k, c in (inject or {}).items():
        sim.inject(k, c)
    sim.start()
    try:
        rep = run(Config(port=sim.port, max_messages=n, max_seconds=20, out_dir=tmp_path, quiet=True, read_timeout=0.5))
    finally:
        sim.stop()
    return rep


def test_tp01_adquisicion_periodica_e_identificacion(tmp_path):
    rep = run_with_sim(tmp_path, n=25)
    rows = list(csv.DictReader(open(tmp_path / "data.csv")))
    assert rep["mensajes_recibidos"] == 25 and rep["mensajes_validos"] == 25
    assert {r["device_id"] for r in rows} == {"ENV-001"}
    seqs = [int(r["seq"]) for r in rows]
    assert seqs == sorted(seqs)


def test_tp02_validacion_trama_valida_y_tipos():
    good = (json.dumps(build_frame("ENV-001", 1, 24, 55, 3.7)) + "\n").encode().strip()
    assert parse_frame(good)["device_id"] == "ENV-001"
    bad = json.loads(good); bad["seq"] = "uno"
    with pytest.raises(ValidationError) as e:
        parse_frame(json.dumps(bad).encode())
    assert e.value.code == "BAD_TYPE"
    with pytest.raises(ValidationError) as e:
        parse_frame(b'{"device_id": "x; rm -rf /", "seq":1}')
    assert e.value.code in ("MISSING_FIELD", "BAD_TYPE")


def test_tp03_clasificacion_normal_y_anomala(tmp_path):
    rep = run_with_sim(tmp_path, n=30, inject={"anomaly": 4})
    assert rep["anomalias_detectadas"] == 4 and rep["mensajes_validos"] == 30
    assert logic.classify({"temp_c": 24, "hum_pct": 50, "volt_v": 3.7})[0] == "NORMAL"
    assert logic.classify({"temp_c": 24, "hum_pct": 50, "volt_v": 2.5}) == ("ANOMALIA", ["VOLTAJE_BAJO"])


def test_tp04_consulta_recursos_so():
    snap = os_info.snapshot(".")
    recursos = [k for k in ("cpu_pct", "mem_pct", "disk_free_gb", "pid", "env_hsf", "os") if snap.get(k) is not None]
    assert len(recursos) >= 2 and "disk_free_gb" in recursos
    assert os_info.assess({"cpu_pct": 99, "mem_pct": 10, "disk_free_gb": 0.1}) == ["CPU_SATURADA", "DISCO_BAJO"]


def test_tp05_persistencia_csv_y_reporte(tmp_path):
    rep = run_with_sim(tmp_path, n=20)
    rows = list(csv.DictReader(open(tmp_path / "data.csv")))
    assert len(rows) == rep["mensajes_validos"] == 20
    assert (tmp_path / "report.json").exists() and (tmp_path / "report.md").exists()
    log = (tmp_path / "events.log").read_text()
    assert "INFO" in log and "evento=TRAMA_OK" in log and "resultado=" in log


def test_tp06_fallo_formato_incorrecto(tmp_path):
    rep = run_with_sim(tmp_path, n=30, inject={"badjson": 3})
    assert rep["rechazados_por_codigo"] == {"BAD_FORMAT": 3}
    assert rep["mensajes_validos"] == 27  # el sistema sigue operando


def test_tp07_fallo_dato_corrupto_y_fuera_de_rango(tmp_path):
    rep = run_with_sim(tmp_path, n=30, inject={"corrupt": 2, "badrange": 2})
    assert rep["rechazados_por_codigo"] == {"BAD_CRC": 2, "OUT_OF_RANGE": 2}
    assert rep["mensajes_validos"] == 26


def test_tp08_perdida_de_comunicacion_y_recuperacion(tmp_path):
    sim = DeviceSimulator(interval=0.02)
    sim.start()
    holder = {}
    t = threading.Thread(target=lambda: holder.update(
        rep=run(Config(port=sim.port, max_messages=80, max_seconds=25, out_dir=tmp_path, quiet=True, read_timeout=0.5))))
    t.start()
    time.sleep(0.6); sim.stop(); time.sleep(1.0); sim.start()
    t.join(30); sim.stop()
    rep = holder["rep"]
    assert rep["errores_conexion"] >= 1 and rep["reintentos_conexion"] >= 1
    assert len(rep["recuperaciones_s"]) >= 1 and rep["recuperaciones_s"][0] < 5
    assert rep["mensajes_perdidos_estimados"] > 0 and rep["mensajes_recibidos"] == 80


def test_tp09_ruta_inaccesible_buffer_y_recuperacion(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("soy un archivo, no un directorio")
    store = CsvStore(blocked / "data.csv")
    row = dict.fromkeys(__import__("app.persistence", fromlist=["FIELDS"]).FIELDS, 1)
    assert store.write(row) is False and store.errors == 1 and len(store.buffer) == 1
    blocked.unlink(); blocked.mkdir()
    assert store.write(row) is True and len(store.buffer) == 0
    assert len(list(csv.DictReader(open(blocked / "data.csv")))) == 2
