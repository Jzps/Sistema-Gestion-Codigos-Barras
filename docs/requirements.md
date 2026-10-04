# Requisitos — SGCBP V1

**SGCBP**: Sistema de Gestión de Códigos de Barras y Pesos.

## Problema

Una persona escanea productos con lector de códigos de barras y registra su
peso manualmente. Objetivo: que el peso se introduzca **una sola vez** por
código; los escaneos posteriores recuperan el peso automáticamente y todo
queda en un historial exportable a Excel.

## Alcance de la V1 (Fases 1 y 2)

- **Fase 1**: PostgreSQL local (Docker), API FastAPI, frontend Angular,
  comunicación extremo a extremo, pantalla de escaneo funcional.
- **Fase 2**: autenticación, usuarios, sesión, separación lógica por
  workspace, historial, exportación XLSX.

## Fuera de alcance en V1

- Fase 3: despliegue (Neon, Render, frontend público).
- Fase 4: parser GS1 completo (GTIN, peso embebido, fechas, seriales, lotes),
  estadísticas, gráficos, chatbot, IA, app móvil.
- Microservicios, Kubernetes, Redis, colas, WebSockets, storage en la nube.

## Requisitos funcionales

| ID    | Requisito                                                            | Estado V1 |
| ----- | -------------------------------------------------------------------- | --------- |
| RF-01 | Login con usuario y contraseña                                       | ✅        |
| RF-02 | Logout                                                               | ✅        |
| RF-03 | Recuperar sesión del usuario actual (`GET /api/auth/me`)             | ✅        |
| RF-04 | Acceso exclusivo a datos del propio workspace                        | ✅        |
| RF-05 | Escaneo con lector USB (modo teclado + Enter)                        | ✅        |
| RF-06 | Entrada manual de códigos                                            | ✅        |
| RF-07 | Verificar si el código existe en el workspace                        | ✅        |
| RF-08 | Si no existe, solicitar peso y unidad                                | ✅        |
| RF-09 | Conversión KG ↔ LB (1 LB = 0.45359237 KG)                            | ✅        |
| RF-10 | Crear producto                                                       | ✅        |
| RF-11 | Registrar el escaneo                                                 | ✅        |
| RF-12 | Recuperar producto existente                                         | ✅        |
| RF-13 | No volver a pedir el peso si el código ya existe                     | ✅        |
| RF-14 | Cada escaneo crea un evento en SCANS                                 | ✅        |
| RF-15 | Historial: fecha/hora, código, producto, peso, unidad, usuario       | ✅        |
| RF-16 | Historial limitado al workspace autenticado                          | ✅        |
| RF-17 | Exportar historial                                                   | ✅        |
| RF-18 | Exportación `.xlsx` válida                                           | ✅        |
| RF-19 | Columnas legibles en el Excel                                        | ✅        |
| RF-20 | Rechazo de accesos no autenticados (401)                             | ✅        |
| RF-21 | Imposibilidad de leer datos de otro workspace (404 sin filtrar info) | ✅        |

## Reglas de dominio

1. **Identidad del producto (V1)**: unicidad `(workspace_id, barcode_raw)`.
   El código se guarda íntegro en `barcode_raw`. Sin parser GS1 todavía;
   `barcode_type` y `product_identifier` quedan preparados para la Fase 4.
2. **Peso**: unidades `KG`/`LB`. Se persiste el valor y unidad originales
   (`weight_value`, `weight_unit`) y el peso normalizado (`weight_kg`).
   Cálculos con `Decimal`, nunca float. El backend es la autoridad: si el
   producto ya existe, se ignora cualquier peso enviado.
3. **Escaneo**: cada lectura (nueva o repetida) crea exactamente un registro
   en `scans` con usuario y timestamp.
4. **Aislamiento**: una sola base de datos compartida; separación lógica por
   `workspace_id`. El `workspace_id` se deriva SIEMPRE del usuario
   autenticado, nunca del cliente.
5. **Seguridad**: Argon2id para contraseñas, JWT en cookie HttpOnly
   (`SameSite=Lax`; `Secure` configurable por entorno), validación Pydantic
   en toda entrada, CORS explícito, sin stack traces al cliente.
