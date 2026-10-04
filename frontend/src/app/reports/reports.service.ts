import { Injectable } from '@angular/core';

import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ReportsService {
  /**
   * Descarga el historial en .xlsx. El archivo lo genera el backend bajo
   * demanda; la cookie de sesión viaja automáticamente con la navegación.
   */
  downloadScansXlsx(): void {
    window.location.href = `${environment.apiUrl}/reports/scans.xlsx`;
  }
}
