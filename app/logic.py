"""Clasificacion de condicion normal / anomala (RF04)."""
LIMITS = {"temp_c_max": 35.0, "hum_pct_max": 85.0, "volt_v_min": 3.0}


def classify(frame: dict):
    reasons = []
    if frame["temp_c"] > LIMITS["temp_c_max"]:
        reasons.append("TEMP_ALTA")
    if frame["hum_pct"] > LIMITS["hum_pct_max"]:
        reasons.append("HUMEDAD_ALTA")
    if frame["volt_v"] < LIMITS["volt_v_min"]:
        reasons.append("VOLTAJE_BAJO")
    return ("ANOMALIA" if reasons else "NORMAL"), reasons
