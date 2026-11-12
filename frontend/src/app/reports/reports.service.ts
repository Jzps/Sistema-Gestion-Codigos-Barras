import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ReportsService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  /**
   * Descarga el historial en .xlsx. El archivo lo genera el backend bajo
   * demanda.
   *
   * Se usa HttpClient y NO `window.location.href` por dos motivos:
   *
   * 1. La peticion sale como XHR con `credentials: 'include'`, el mismo
   *    mecanismo que el resto de llamadas de la aplicacion (Productos,
   *    Historial, escaneo...). Es el canal con el que la cookie de sesion
   *    viaja de forma fiable.
   * 2. `window.location.href` es una NAVEGACION de nivel superior a otro
   *    origen: el navegador aplica ahi politicas de cookies mas restrictivas
   *    (y en algunas configuraciones la cookie no se envia), y si la API
   *    responde 401 el usuario abandona la SPA y aterriza en una pagina JSON
   *    con el error, en lugar de ver un aviso dentro de la aplicacion.
   *
   * La autenticacion del endpoint NO se toca: sigue exigiendo la cookie de
   * sesion valida en el backend.
   */
  downloadScansXlsx(): Observable<Blob> {
    return this.http.get(`${this.api}/reports/scans.xlsx`, {
      responseType: 'blob',
      withCredentials: true,
    });
  }
}
