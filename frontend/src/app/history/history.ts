import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';

import { ReportsService } from '../reports/reports.service';
import { describeApiError } from '../shared/api-error';
import { ScanRow } from '../shared/models';
import { HistoryService } from './history.service';

/**
 * Historial de escaneos: listado, exportación y eliminación de eventos
 * incorrectos (DELETE). Los scans no se editan: la corrección es eliminar
 * y volver a escanear. Eliminar un scan nunca elimina el producto.
 */
@Component({
  selector: 'app-history',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './history.html',
  styleUrl: './history.scss',
})
export class History implements OnInit {
  private readonly historyService = inject(HistoryService);
  private readonly reportsService = inject(ReportsService);

  readonly rows = signal<ScanRow[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  /** Scan pendiente de confirmación de borrado. */
  readonly deleting = signal<ScanRow | null>(null);
  readonly saving = signal(false);
  /** Exportación a Excel en curso. */
  readonly exporting = signal(false);
  readonly actionError = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  /**
   * Exporta el historial a .xlsx.
   *
   * La descarga la hace el navegador a partir del Blob que devuelve la API
   * (ver ReportsService). Si la API responde 401 (sesión no válida) se
   * muestra el aviso dentro de la aplicación, sin abandonar la SPA.
   */
  export(): void {
    if (this.exporting()) return;
    this.exporting.set(true);
    this.clearMessages();
    this.reportsService.downloadScansXlsx().subscribe({
      next: (blob) => {
        this.exporting.set(false);
        this.saveBlob(blob, this.xlsxFileName());
      },
      error: (err) => {
        this.exporting.set(false);
        this.actionError.set(
          describeApiError(err, 'No se pudo exportar el historial a Excel'),
        );
      },
    });
  }

  /** Guarda el Blob como fichero .xlsx y dispara la descarga. */
  private saveBlob(blob: Blob, fileName: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  /**
   * Nombre del fichero exportado. Mismo formato que genera el backend
   * (scans_AAAAMMDD_HHMMSS.xlsx). No se lee la cabecera Content-Disposition
   * porque, al ser el frontend y la API de orígenes distintos, el navegador
   * solo expone las cabeceras que CORS marque como públicas.
   */
  private xlsxFileName(): string {
    const now = new Date();
    const pad = (value: number) => String(value).padStart(2, '0');
    const stamp =
      `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
      `_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
    return `scans_${stamp}.xlsx`;
  }

  startDelete(row: ScanRow): void {
    this.clearMessages();
    this.deleting.set(row);
  }

  cancelDelete(): void {
    this.deleting.set(null);
  }

  confirmDelete(): void {
    const row = this.deleting();
    if (!row || this.saving()) return;

    this.saving.set(true);
    this.clearMessages();
    this.historyService.delete(row.id).subscribe({
      next: () => {
        this.saving.set(false);
        this.deleting.set(null);
        // Se quita de la lista al instante; el producto no se toca.
        this.rows.update((list) => list.filter((r) => r.id !== row.id));
        this.flash(`Registro de ${row.barcode_raw} eliminado del historial`);
      },
      error: (err) => {
        this.saving.set(false);
        this.deleting.set(null);
        this.actionError.set(describeApiError(err, 'No se pudo eliminar el registro'));
        // 404: el registro ya no existe -> refrescar para ver el estado real.
        if (err?.status === 404) {
          this.load();
        }
      },
    });
  }

  private load(): void {
    this.historyService.list(200).subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(describeApiError(err, 'No se pudo cargar el historial'));
        this.loading.set(false);
      },
    });
  }

  private clearMessages(): void {
    this.actionError.set(null);
    this.successMessage.set(null);
  }

  private flash(message: string): void {
    this.successMessage.set(message);
    setTimeout(() => {
      if (this.successMessage() === message) this.successMessage.set(null);
    }, 4000);
  }
}
