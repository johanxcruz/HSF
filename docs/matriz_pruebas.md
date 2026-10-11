# Matriz de pruebas (resultado de `python -m pytest -q tests`: 9 passed)

| ID | Prueba | Entrada / condición | Resultado esperado | Resultado real | Estado |
|---|---|---|---|---|---|
| TP-01 | Recepción periódica e identificación | 25 tramas normales | 25 válidas, `device_id` = ENV-001, `seq` creciente | 25 recibidas, 25 válidas | OK |
| TP-02 | Validación de trama | `seq` como texto; `device_id` con comandos | `BAD_TYPE` / rechazo | `BAD_TYPE` y rechazo | OK |
| TP-03 | Normal vs. anómala | 4 anomalías inyectadas en 30 tramas | 4 detectadas | 4 detectadas | OK |
| TP-04 | Recursos del SO | CPU, memoria, disco, PID, entorno | ≥ 2 recursos; alertas por umbral | 6 campos leídos; alertas correctas | OK |
| TP-05 | CSV y reporte | 20 tramas | 20 filas + `report.json/.md` + log | 20 filas, log y reporte | OK |
| TP-06 | Fallo: JSON incorrecto | 3 tramas rotas | 3 `BAD_FORMAT`; sigue operando | 3 rechazos, 27 válidas | OK |
| TP-07 | Fallo: CRC y rango | 2 CRC alterado, 2 con 999 °C | 2 `BAD_CRC`, 2 `OUT_OF_RANGE` | 2 y 2; 26 válidas | OK |
| TP-08 | Fallo: pérdida de comunicación | dispositivo detenido 1 s | reconexión < 5 s | 1 error de conexión; recuperó en 1,4 s | OK |
| TP-09 | Fallo: ruta inaccesible | directorio no escribible y luego restaurado | buffer y vuelco sin pérdida | 2 filas, ninguna perdida | OK |
