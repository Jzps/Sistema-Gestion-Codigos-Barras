import { Component, ElementRef, OnInit, ViewChild, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe, DecimalPipe } from '@angular/common';

import { AutofocusDirective } from '../shared/autofocus.directive';
import { ScanResponse, ScanRow } from '../shared/models';
import { ScanService } from './scan.service';

/**
 * Pantalla principal de la aplicación.
 *
 * Flujo:
 *  - Código nuevo  → backend responde needs_weight → se pide peso/unidad →
 *    se reenvía → created.
 *  - Código conocido → existing → se muestra el peso al instante.
 *
 * Tras cada escaneo el campo de código se limpia y recupera el foco para
 * encadenar lecturas rápidas con el lector USB (que actúa como teclado).
 */
@Component({
  selector: 'app-scanner',
  imports: [FormsModule, DatePipe, DecimalPipe, AutofocusDirective],
  templateUrl: './scanner.html',
  styleUrl: './scanner.scss',
})
export class Scanner implements OnInit {
  private readonly scanService = inject(ScanService);

  @ViewChild('barcodeInput') private barcodeInput?: ElementRef<HTMLInputElement>;

  barcode = '';

  /** Código nuevo a la espera de que el usuario introduzca el peso. */
  readonly pendingBarcode = signal<string | null>(null);
  weightValue: number | null = null;
  weightUnit: 'KG' | 'LB' = 'KG';
  productName = '';

  /** Último escaneo procesado (confirmación visible). */
  readonly result = signal<ScanResponse | null>(null);
  readonly recent = signal<ScanRow[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.refreshRecent();
  }

  onScan(): void {
    const barcode = this.barcode.trim();
    if (!barcode || this.loading()) return;
    this.send({ barcode });
  }

  /** Segundo paso para códigos nuevos: llega el peso y se completa el alta. */
  onSubmitWeight(): void {
    const barcode = this.pendingBarcode();
    if (!barcode || this.loading()) return;
    if (!this.weightValue || this.weightValue <= 0) {
      this.error.set('Introduce un peso válido mayor que cero');
      return;
    }
    this.send({
      barcode,
      weight_value: this.weightValue,
      weight_unit: this.weightUnit,
      product_name: this.productName.trim() || null,
    });
  }

  cancelWeight(): void {
    this.resetWeightForm();
    this.focusBarcode();
  }

  private send(payload: Parameters<ScanService['scan']>[0]): void {
    this.loading.set(true);
    this.error.set(null);
    this.scanService.scan(payload).subscribe({
      next: (res) => {
        this.loading.set(false);
        if (res.status === 'needs_weight') {
          this.pendingBarcode.set(res.barcode);
          this.result.set(null);
        } else {
          this.result.set(res);
          this.resetWeightForm();
          this.refreshRecent();
        }
        this.barcode = '';
        this.focusBarcode();
      },
      error: () => {
        this.loading.set(false);
        this.error.set('No se pudo procesar el escaneo. Inténtalo de nuevo.');
        this.barcode = '';
        this.focusBarcode();
      },
    });
  }

  private resetWeightForm(): void {
    this.pendingBarcode.set(null);
    this.weightValue = null;
    this.weightUnit = 'KG';
    this.productName = '';
  }

  private refreshRecent(): void {
    this.scanService.listRecent(5).subscribe({
      next: (rows) => this.recent.set(rows),
      error: () => {},
    });
  }

  private focusBarcode(): void {
    setTimeout(() => this.barcodeInput?.nativeElement.focus());
  }
}
