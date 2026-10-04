import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { ScanPayload, ScanResponse, ScanRow } from '../shared/models';

@Injectable({ providedIn: 'root' })
export class ScanService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  /**
   * Entrada única del flujo de escaneo. Toda la lógica (¿existe?, ¿pedir
   * peso?, ¿crear producto?) la decide el backend; aquí solo se envía el
   * código y, cuando se pide, el peso.
   */
  scan(payload: ScanPayload): Observable<ScanResponse> {
    return this.http.post<ScanResponse>(`${this.api}/scans`, payload);
  }

  /** Últimos escaneos del workspace (para el panel de actividad reciente). */
  listRecent(limit = 5): Observable<ScanRow[]> {
    return this.http.get<ScanRow[]>(`${this.api}/scans`, { params: { limit } });
  }
}
