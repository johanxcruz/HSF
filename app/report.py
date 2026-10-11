"""Metricas, indicadores tecnicos y reporte de ejecucion (RF08)."""
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Metrics:
    lines: int = 0
    valid: int = 0
    anomalies: int = 0
    unparseable: int = 0
    gaps: int = 0
    timeouts: int = 0
    retries: int = 0
    connection_errors: int = 0
    storage_errors: int = 0
    invalid: Counter = field(default_factory=Counter)
    latencies: list = field(default_factory=list)
    proc_times: list = field(default_factory=list)
    recoveries: list = field(default_factory=list)
    prev_seq: int = None

    def note_seq(self, seq):
        if isinstance(seq, int) and not isinstance(seq, bool):
            if self.prev_seq is not None and seq > self.prev_seq + 1:
                self.gaps += seq - self.prev_seq - 1
            if self.prev_seq is None or seq > self.prev_seq:
                self.prev_seq = seq


def _stats(vals):
    if not vals:
        return {"n": 0, "media": None, "p95": None, "max": None}
    s = sorted(vals)
    return {"n": len(s), "media": round(sum(s) / len(s), 3),
            "p95": round(s[min(len(s) - 1, int(0.95 * len(s)))], 3), "max": round(s[-1], 3)}


def build(m: Metrics, cfg, os_snap, elapsed, store) -> dict:
    lost = max(0, m.gaps - m.unparseable)
    expected = m.lines + lost
    events = m.lines + m.connection_errors + m.storage_errors
    errors = sum(m.invalid.values()) + m.connection_errors + m.storage_errors
    avail = 100 * m.lines / expected if expected else 0.0
    valid_pct = 100 * m.valid / m.lines if m.lines else 0.0
    err_pct = 100 * errors / events if events else 0.0
    rec_max = max(m.recoveries) if m.recoveries else 0.0
    ind = {
        "disponibilidad_comunicacion_pct": {"valor": round(avail, 2), "meta": ">= 95", "cumple": avail >= 95},
        "datos_validos_pct": {"valor": round(valid_pct, 2), "meta": ">= 98", "cumple": valid_pct >= 98},
        "tasa_errores_pct": {"valor": round(err_pct, 2), "meta": "<= 5", "cumple": err_pct <= 5},
        "tiempo_recuperacion_s": {"valor": round(rec_max, 3), "meta": "<= 5 (definido por caso)",
                                  "cumple": rec_max <= 5},
    }
    return {
        "duracion_s": round(elapsed, 2),
        "mensajes_recibidos": m.lines, "mensajes_validos": m.valid,
        "mensajes_perdidos_estimados": lost,
        "rechazados_por_codigo": dict(m.invalid),
        "anomalias_detectadas": m.anomalies,
        "errores_conexion": m.connection_errors, "reintentos_conexion": m.retries,
        "errores_almacenamiento": m.storage_errors, "filas_descartadas_buffer": store.dropped,
        "latencia_ms": _stats(m.latencies), "procesamiento_ms": _stats(m.proc_times),
        "recuperaciones_s": [round(r, 3) for r in m.recoveries],
        "indicadores": ind, "so": os_snap,
    }


def write(report: dict, out_dir: Path):
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    r, ind, so = report, report["indicadores"], report["so"]
    lines = [
        "# Reporte de ejecucion", "",
        f"- Duracion: {r['duracion_s']} s | SO: {so['os']} {so['release']} | Python {so['python']} | PID {so['pid']}",
        f"- Mensajes recibidos: {r['mensajes_recibidos']} | validos: {r['mensajes_validos']} "
        f"| perdidos (estimado): {r['mensajes_perdidos_estimados']}",
        f"- Rechazados por codigo: {r['rechazados_por_codigo'] or 'ninguno'}",
        f"- Anomalias de proceso detectadas: {r['anomalias_detectadas']}",
        f"- Errores de conexion: {r['errores_conexion']} | reintentos: {r['reintentos_conexion']} "
        f"| errores de almacenamiento: {r['errores_almacenamiento']}",
        f"- Latencia (ms): {r['latencia_ms']}", f"- Procesamiento (ms): {r['procesamiento_ms']}",
        f"- Recuperaciones (s): {r['recuperaciones_s'] or 'n/a'}", "",
        "| Indicador | Valor | Meta | Cumple |", "|---|---|---|---|",
    ]
    for k, v in ind.items():
        lines.append(f"| {k} | {v['valor']} | {v['meta']} | {'SI' if v['cumple'] else 'NO'} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
