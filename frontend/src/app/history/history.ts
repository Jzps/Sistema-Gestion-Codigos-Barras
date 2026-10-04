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
  readonly actionError = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  export(): void {
    this.reportsService.downloadScansXlsx();
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
