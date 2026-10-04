import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { ScanRow } from '../shared/models';

@Injectable({ providedIn: 'root' })
export class HistoryService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  /** Historial del workspace autenticado, más reciente primero. */
  list(limit = 200): Observable<ScanRow[]> {
    return this.http.get<ScanRow[]>(`${this.api}/scans`, { params: { limit } });
  }

  /** DELETE /api/scans/{id}. Elimina solo el evento; el producto asociado
   * no se toca. No existe PATCH de scans (eventos inmutables). */
  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/scans/${id}`);
  }
}
