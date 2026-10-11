"""Validacion de estructura, tipo, integridad (CRC) y rango de cada trama (RF03)."""
import json
import re
import zlib

MAX_LINE = 4096
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
RANGES = {"temp_c": (-40.0, 85.0), "hum_pct": (0.0, 100.0), "volt_v": (0.0, 5.5)}
REQUIRED = ("device_id", "seq", "ts", "temp_c", "hum_pct", "volt_v", "crc")


class ValidationError(Exception):
    def __init__(self, code, detail="", frame=None):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.frame = code, detail, frame


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _crc(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"{zlib.crc32(raw):08x}"


def parse_frame(line: bytes) -> dict:
    if len(line) > MAX_LINE:
        raise ValidationError("BAD_FORMAT", "trama demasiado larga")
    try:
        obj = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValidationError("BAD_FORMAT", str(e))
    if not isinstance(obj, dict):
        raise ValidationError("BAD_FORMAT", "se esperaba un objeto JSON")
    missing = [k for k in REQUIRED if k not in obj]
    if missing:
        raise ValidationError("MISSING_FIELD", ",".join(missing), obj)
    if not (isinstance(obj["device_id"], str) and DEVICE_ID_RE.match(obj["device_id"])):
        raise ValidationError("BAD_TYPE", "device_id invalido", obj)
    if not (isinstance(obj["seq"], int) and not isinstance(obj["seq"], bool)):
        raise ValidationError("BAD_TYPE", "seq no entero", obj)
    for k in ("ts", *RANGES):
        if not _is_num(obj[k]):
            raise ValidationError("BAD_TYPE", f"{k} no numerico", obj)
    payload = {k: v for k, v in obj.items() if k != "crc"}
    if obj["crc"] != _crc(payload):
        raise ValidationError("BAD_CRC", "integridad no coincide", obj)
    for k, (lo, hi) in RANGES.items():
        if not lo <= obj[k] <= hi:
            raise ValidationError("OUT_OF_RANGE", f"{k}={obj[k]} fuera de [{lo},{hi}]", obj)
    return obj
