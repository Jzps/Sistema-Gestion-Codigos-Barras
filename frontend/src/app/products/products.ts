import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { describeApiError } from '../shared/api-error';
import { Product, ProductUpdate } from '../shared/models';
import { ProductsService } from './products.service';

/**
 * Gestión de productos del workspace: listar, editar (PATCH) y eliminar
 * (DELETE, solo si el backend confirma que no tienen escaneos).
 *
 * Toda la lógica de dominio (recálculo de weight_kg, barcode duplicado,
 * producto con historial) vive en el backend; aquí solo se muestran sus
 * respuestas y errores.
 */
@Component({
  selector: 'app-products',
  imports: [DatePipe, DecimalPipe, FormsModule],
  templateUrl: './products.html',
  styleUrl: './products.scss',
})
export class Products implements OnInit {
  private readonly productsService = inject(ProductsService);

  readonly products = signal<Product[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  /** Producto en edición (tarjeta inline) y campos del formulario. */
  readonly editing = signal<Product | null>(null);
  editBarcode = '';
  editType = '';
  editIdentifier = '';
  editName = '';
  editWeight: number | null = null;
  editUnit: 'KG' | 'LB' = 'KG';

  /** Producto pendiente de confirmación de borrado. */
  readonly deleting = signal<Product | null>(null);

  readonly saving = signal(false);
  readonly actionError = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.productsService.list().subscribe({
      next: (products) => {
        this.products.set(products);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(describeApiError(err, 'No se pudo cargar la lista de productos'));
        this.loading.set(false);
      },
    });
  }

  // ------------------------- Edición -------------------------

  startEdit(product: Product): void {
    this.clearMessages();
    this.deleting.set(null);
    this.editing.set(product);
    this.editBarcode = product.barcode_raw;
    this.editType = product.barcode_type ?? '';
    this.editIdentifier = product.product_identifier ?? '';
    this.editName = product.product_name ?? '';
    this.editWeight = Number(product.weight_value);
    this.editUnit = product.weight_unit;
  }

  cancelEdit(): void {
    this.editing.set(null);
  }

  saveEdit(): void {
    const product = this.editing();
    if (!product || this.saving()) return;
    if (!this.editBarcode.trim()) {
      this.actionError.set('El código de barras no puede estar vacío');
      return;
    }
    if (!this.editWeight || this.editWeight <= 0) {
      this.actionError.set('Introduce un peso válido mayor que cero');
      return;
    }

    const payload: ProductUpdate = {
      barcode_raw: this.editBarcode.trim(),
      barcode_type: this.editType.trim() || null,
      product_identifier: this.editIdentifier.trim() || null,
      product_name: this.editName.trim() || null,
      weight_value: this.editWeight,
      weight_unit: this.editUnit,
    };

    this.saving.set(true);
    this.clearMessages();
    this.productsService.update(product.id, payload).subscribe({
      next: (updated) => {
        this.saving.set(false);
        this.editing.set(null);
        // Actualización en caliente: se sustituye la fila sin recargar.
        this.products.update((list) =>
          list.map((p) => (p.id === updated.id ? updated : p)),
        );
        this.flash(`Producto ${updated.barcode_raw} actualizado correctamente`);
      },
      error: (err) => {
        this.saving.set(false);
        this.actionError.set(describeApiError(err, 'No se pudo guardar el producto'));
      },
    });
  }

  // ------------------------- Eliminación -------------------------

  startDelete(product: Product): void {
    this.clearMessages();
    this.editing.set(null);
    this.deleting.set(product);
  }

  cancelDelete(): void {
    this.deleting.set(null);
  }

  confirmDelete(): void {
    const product = this.deleting();
    if (!product || this.saving()) return;

    this.saving.set(true);
    this.clearMessages();
    this.productsService.delete(product.id).subscribe({
      next: () => {
        this.saving.set(false);
        this.deleting.set(null);
        this.products.update((list) => list.filter((p) => p.id !== product.id));
        this.flash(`Producto ${product.barcode_raw} eliminado correctamente`);
      },
      error: (err) => {
        this.saving.set(false);
        this.deleting.set(null);
        // 409 (tiene escaneos) u otro error: el producto PERMANECE en la lista.
        this.actionError.set(describeApiError(err, 'No se pudo eliminar el producto'));
      },
    });
  }

  // ------------------------- Mensajes -------------------------

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
