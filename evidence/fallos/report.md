# Reporte de ejecucion

- Duracion: 9.8 s | SO: Windows 11 | Python 3.12.6 | PID 19432
- Mensajes recibidos: 160 | validos: 143 | perdidos (estimado): 30
- Rechazados por codigo: {'BAD_CRC': 9, 'BAD_FORMAT': 5, 'OUT_OF_RANGE': 3}
- Anomalias de proceso detectadas: 7
- Errores de conexion: 1 | reintentos: 1 | errores de almacenamiento: 0
- Latencia (ms): {'n': 143, 'media': 0.007, 'p95': 0.0, 'max': 0.511}
- Procesamiento (ms): {'n': 143, 'media': 1.066, 'p95': 1.429, 'max': 1.605}
- Recuperaciones (s): [1.722]

| Indicador | Valor | Meta | Cumple |
|---|---|---|---|
| disponibilidad_comunicacion_pct | 84.21 | >= 95 | NO |
| datos_validos_pct | 89.38 | >= 98 | NO |
| tasa_errores_pct | 11.18 | <= 5 | NO |
| tiempo_recuperacion_s | 1.722 | <= 5 (definido por caso) | SI |
