import { HttpInterceptorFn } from '@angular/common/http';

/**
 * Envía la cookie de sesión en TODAS las llamadas a la API.
 * Sin withCredentials el navegador no adjuntaría la cookie HttpOnly
 * en peticiones al puerto 8000.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) =>
  next(req.clone({ withCredentials: true }));
