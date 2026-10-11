"""Consulta de recursos del sistema operativo y relacion con la operacion (RF06)."""
import os
import platform
import shutil

try:
    import psutil
    psutil.cpu_percent(interval=None)  # cebado: la primera lectura siempre es 0.0
except ImportError:  # degradacion elegante: solo biblioteca estandar
    psutil = None


def snapshot(path="."):
    snap = {
        "os": platform.system(), "release": platform.release(),
        "python": platform.python_version(), "pid": os.getpid(),
        "env_hsf": os.environ.get("HSF_ENV", "dev"),
    }
    if psutil:
        snap["cpu_pct"] = psutil.cpu_percent(interval=None)
        snap["mem_pct"] = psutil.virtual_memory().percent
        snap["proc_rss_mb"] = round(psutil.Process().memory_info().rss / 1e6, 1)
    else:
        load = os.getloadavg()[0] / (os.cpu_count() or 1) * 100 if hasattr(os, "getloadavg") else None
        snap.update(cpu_pct=round(load, 1) if load is not None else None, mem_pct=None, proc_rss_mb=None)
    du = shutil.disk_usage(path)
    snap["disk_free_gb"] = round(du.free / 1e9, 2)
    snap["disk_used_pct"] = round(du.used / du.total * 100, 1)
    return snap


def assess(snap, cpu_limit=90, mem_limit=90, disk_free_min_gb=0.5):
    """Relaciona recursos del SO con el riesgo operativo del sistema."""
    warns = []
    if snap.get("cpu_pct") is not None and snap["cpu_pct"] > cpu_limit:
        warns.append("CPU_SATURADA")
    if snap.get("mem_pct") is not None and snap["mem_pct"] > mem_limit:
        warns.append("MEMORIA_ALTA")
    if snap["disk_free_gb"] < disk_free_min_gb:
        warns.append("DISCO_BAJO")
    return warns
