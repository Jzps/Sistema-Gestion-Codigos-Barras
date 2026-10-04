import { HttpErrorResponse } from '@angular/common/http';

/**
 * Traduce errores HTTP de la API a mensajes comprensibles para el usuario.
 * Punto único de mapeo: los componentes no interpretan códigos de estado.
 *
 * 409/404: el backend ya devuelve `detail` en español y se reutiliza.
 */
export function describeApiError(err: unknown, fallback: string): string {
  if (!(err instanceof HttpErrorResponse)) {
    return fallback;
  }
  const detail = (err.error as { detail?: unknown } | null)?.detail;

  switch (err.status) {
    case 0:
      return 'No se pudo conectar con el servidor. ¿Está el backend en marcha?';
    case 401:
      return 'Tu sesión ha expirado. Vuelve a iniciar sesión.';
    case 404:
      return typeof detail === 'string'
        ? detail
        : 'El registro ya no existe o no está disponible.';
    case 409:
      return typeof detail === 'string' ? detail : 'Conflicto con el estado actual.';
    case 422:
      return 'Datos inválidos: revisa los campos e inténtalo de nuevo.';
    default:
      return fallback;
  }
}
