import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { Product } from '../shared/models';
import { Products } from './products';

const API = environment.apiUrl;

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    barcode_raw: 'P-1',
    barcode_type: null,
    product_identifier: null,
    product_name: 'Producto uno',
    weight_value: '10.0000',
    weight_unit: 'KG',
    weight_kg: '10.000000',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('Products', () => {
  let fixture: ComponentFixture<Products>;
  let component: Products;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Products],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(Products);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  /** Dispara ngOnInit y responde la carga inicial de productos. */
  function flushInitialList(products: Product[] = [makeProduct()]): void {
    fixture.detectChanges();
    httpMock.expectOne(`${API}/products`).flush(products);
    fixture.detectChanges();
  }

  function buttonByText(text: string): HTMLButtonElement | undefined {
    const buttons = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('button'),
    ) as HTMLButtonElement[];
    return buttons.find((b) => b.textContent?.trim().startsWith(text));
  }

  it('muestra las acciones Editar y Eliminar en cada producto', () => {
    flushInitialList();
    expect(buttonByText('Editar')).toBeTruthy();
    expect(buttonByText('Eliminar')).toBeTruthy();
  });

  it('editar llama a PATCH /api/products/{id} y actualiza la fila sin recargar', () => {
    flushInitialList();

    buttonByText('Editar')!.click();
    fixture.detectChanges();
    expect(component.editing()).toBeTruthy();

    component.editName = 'Nombre corregido';
    component.editWeight = 44.09;
    component.editUnit = 'LB';
    buttonByText('Guardar')!.click();

    const req = httpMock.expectOne(`${API}/products/1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body.product_name).toBe('Nombre corregido');
    expect(req.request.body.weight_value).toBe(44.09);
    expect(req.request.body.weight_unit).toBe('LB');

    // El backend devuelve weight_kg ya recalculado: la UI solo lo muestra.
    req.flush(
      makeProduct({
        product_name: 'Nombre corregido',
        weight_value: '44.0900',
        weight_unit: 'LB',
        weight_kg: '19.998888',
      }),
    );
    fixture.detectChanges();

    expect(component.editing()).toBeNull(); // formulario cerrado
    expect(component.products()[0].product_name).toBe('Nombre corregido');
    expect(component.products()[0].weight_kg).toBe('19.998888');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Nombre corregido');
  });

  it('error 409 al editar (barcode duplicado) muestra mensaje y mantiene el formulario', () => {
    flushInitialList();
    component.startEdit(makeProduct());
    component.editBarcode = 'P-DUPLICADO';
    component.saveEdit();

    const req = httpMock.expectOne(`${API}/products/1`);
    req.flush(
      { detail: 'Ya existe un producto con ese código en este workspace' },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();

    expect(component.actionError()).toContain('Ya existe un producto');
    expect(component.editing()).toBeTruthy(); // el formulario sigue abierto
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Ya existe un producto',
    );
  });

  it('cancelar una edición no modifica el producto', () => {
    flushInitialList();
    component.startEdit(makeProduct());
    component.editName = 'Cambio descartado';
    component.cancelEdit();

    expect(component.editing()).toBeNull();
    expect(component.products()[0].product_name).toBe('Producto uno');
    httpMock.expectNone(`${API}/products/1`);
  });

  it('eliminar llama a DELETE /api/products/{id} y quita la fila', () => {
    flushInitialList();

    buttonByText('Eliminar')!.click();
    fixture.detectChanges();
    expect(component.deleting()).toBeTruthy(); // pide confirmación

    buttonByText('Sí, eliminar')!.click();
    const req = httpMock.expectOne(`${API}/products/1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null, { status: 204, statusText: 'No Content' });
    fixture.detectChanges();

    expect(component.products().length).toBe(0);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Todavía no hay productos',
    );
  });

  it('error 409 al eliminar (tiene escaneos) muestra aviso y el producto permanece', () => {
    flushInitialList();
    component.startDelete(makeProduct());
    component.confirmDelete();

    const req = httpMock.expectOne(`${API}/products/1`);
    req.flush(
      { detail: 'El producto tiene 2 escaneo(s) registrados. Elimina primero los escaneos.' },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();

    expect(component.actionError()).toContain('tiene 2 escaneo(s)');
    expect(component.products().length).toBe(1); // NO desaparece de la tabla
  });
});
