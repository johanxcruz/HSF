# Práctica HSF: integración Hardware – Firmware – Software

Prototipo de sistema de información que captura telemetría de un dispositivo (simulado), la valida y procesa en Python,
consulta recursos del sistema operativo, persiste en CSV y genera un reporte. Integración de Sistemas de Información 2026-2,
Universidad Santo Tomás – Segundo corte.

**Autor:** [nombre y código] · **Programa:** Ingeniería en Informática

## Flujo
`Hardware (sensor) → Firmware (ENV-001 simulado) → TCP/IP → Sistema operativo → Python → CSV / log / reporte → Usuario`

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Firmware (simulado) | `firmware_sim/device_sim.py` | 3 variables (temperatura, humedad, voltaje), `device_id`, `seq`, CRC32, inyección de anomalías y fallos |
| Adquisición | `app/acquisition.py` | Cliente TCP con timeout y buffer acotado |
| Validación | `app/validation.py` | Estructura, tipo, CRC y rango (`BAD_FORMAT`, `BAD_TYPE`, `BAD_CRC`, `OUT_OF_RANGE`) |
| Lógica | `app/logic.py` | Clasificación NORMAL / ANOMALÍA |
| SO | `app/os_info.py` | CPU, memoria, disco, PID, variable de entorno |
| Persistencia | `app/persistence.py` | CSV con buffer en memoria si falla la escritura |
| Reporte y estado | `app/report.py`, `app/main.py` | Indicadores, `report.json/.md`, estado de integración, logs |

## Protocolo
Una línea JSON (UTF-8, `\n`) por muestra:
`{"device_id":"ENV-001","seq":42,"ts":1791732053.81,"temp_c":23.69,"hum_pct":57.05,"volt_v":3.691,"crc":"1db0fa5c"}`.
El CRC32 se calcula sobre el payload ordenado (sin el campo `crc`).

## Ejecución
```bash
pip install -r requirements.txt
python -m pytest -q tests          # matriz de pruebas TP-01 a TP-09
python run_demo.py                 # genera evidence/baseline y evidence/fallos

# Manual, en dos terminales
python -m firmware_sim.device_sim --port 5000 --anomaly-every 20 --corrupt-every 17
python -m app.main --port 5000 --max-messages 100 --out-dir runs/manual
```

## Requisitos cubiertos
RF01 identificar dispositivo · RF02 recepción periódica · RF03 validación · RF04 clasificación · RF05 eventos y errores ·
RF06 consulta del SO · RF07 CSV · RF08 reporte · RF09 recuperación de fallas · RF10 estado de integración.
Matriz de pruebas en `docs/matriz_pruebas.md`.

## Seguridad
Sin `subprocess` ni shell. `device_id` validado con expresión regular, trama máxima de 4 KB, buffer máximo de 64 KB,
escucha solo en `127.0.0.1`.

## Portabilidad Windows / Linux
Rutas con `pathlib`; `os.getloadavg` solo existe en Linux (la app usa `psutil` y degrada si no está instalado);
permisos distintos (ACL frente a `chmod`); con hardware real el puerto serie es `COMx` en Windows y `/dev/ttyUSBx` en Linux.

## Escalar a varios dispositivos
Un servidor concurrente (`asyncio` o broker MQTT) con una tarea por `device_id`, un CSV o base de series de tiempo por dispositivo
y métricas separadas.

## Limitaciones conocidas
- La latencia usa el reloj del mismo equipo; con equipos distintos hay que sincronizar relojes (NTP).
- El tiempo de recuperación se mide desde la detección de la caída hasta la primera trama válida.
- CRC32 detecta corrupción accidental, no manipulación (para eso, HMAC).
