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
}
