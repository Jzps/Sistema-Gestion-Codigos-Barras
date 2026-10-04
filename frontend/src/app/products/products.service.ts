import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { Product, ProductUpdate } from '../shared/models';

@Injectable({ providedIn: 'root' })
export class ProductsService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  list(): Observable<Product[]> {
    return this.http.get<Product[]>(`${this.api}/products`);
  }

  /** Corrección parcial: PATCH /api/products/{id}. El backend recalcula
   * weight_kg; el frontend nunca convierte unidades por su cuenta. */
  update(id: number, payload: ProductUpdate): Observable<Product> {
    return this.http.patch<Product>(`${this.api}/products/${id}`, payload);
  }

  /** DELETE /api/products/{id}. El backend responde 409 si el producto
   * tiene escaneos: la UI debe mostrarlo y mantener el producto en lista. */
  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/products/${id}`);
  }
}
