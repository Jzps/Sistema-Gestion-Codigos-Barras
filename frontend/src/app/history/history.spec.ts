import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { ScanRow } from '../shared/models';
import { History } from './history';

const API = environment.apiUrl;

function makeScan(overrides: Partial<ScanRow> = {}): ScanRow {
  return {
    id: 1,
    scanned_at: '2026-01-01T10:00:00Z',
    product_id: 1,
    user_id: 1,
    username: 'op',
    barcode_raw: 'ABC-1',
    product_name: 'Caja',
    weight_value: '10.0000',
    weight_unit: 'KG',
    weight_kg: '10.000000',
    weight_lb: '22.046226',
    ...overrides,
  };
}

describe('History', () => {
  let fixture: ComponentFixture<History>;
  let component: History;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [History],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(History);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  function flushInitialList(rows: ScanRow[] = [makeScan()]) {
    fixture.detectChanges();
    httpMock.expectOne(`${API}/scans?limit=200`).flush(rows);
    fixture.detectChanges();
  }

  function buttonByText(text: string): HTMLButtonElement | undefined {
    const buttons = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('button'),
    ) as HTMLButtonElement[];
    return buttons.find((b) => b.textContent?.trim().startsWith(text));
  }

  it('muestra la acción Eliminar en cada registro', () => {
    flushInitialList();
    expect(buttonByText('Eliminar')).toBeTruthy();
  });

  it('eliminar un scan pide confirmación, llama a DELETE /api/scans/{id} y desaparece de la lista', () => {
    flushInitialList([makeScan({ id: 7 }), makeScan({ id: 8, barcode_raw: 'ABC-2' })]);

    buttonByText('Eliminar')!.click();
    fixture.detectChanges();
    expect(component.deleting()?.id).toBe(7);

    buttonByText('Sí, eliminar')!.click();
    const req = httpMock.expectOne(`${API}/scans/7`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null, { status: 204, statusText: 'No Content' });
    fixture.detectChanges();

    expect(component.rows().map((r) => r.id)).toEqual([8]);
    // El scan desaparece de la TABLA (el aviso de éxito sí menciona el código).
    const tableText = (fixture.nativeElement as HTMLElement).querySelector('tbody')!
      .textContent!;
    expect(tableText).not.toContain('ABC-1');
    expect(tableText).toContain('ABC-2'); // el resto del historial intacto
  });

  it('error 404 al eliminar muestra aviso y refresca la lista', () => {
    flushInitialList();
    component.startDelete(makeScan());
    component.confirmDelete();

    const req = httpMock.expectOne(`${API}/scans/1`);
    req.flush(
      { detail: 'Escaneo no encontrado' },
      { status: 404, statusText: 'Not Found' },
    );
    fixture.detectChanges();

    expect(component.actionError()).toBe('Escaneo no encontrado');
    // Tras un 404 se recarga el historial para reflejar el estado real.
    httpMock.expectOne(`${API}/scans?limit=200`).flush([]);
    fixture.detectChanges();
    expect(component.rows().length).toBe(0);
  });

  it('cancelar la confirmación no borra nada', () => {
    flushInitialList();
    component.startDelete(makeScan());
    component.cancelDelete();

    expect(component.deleting()).toBeNull();
    expect(component.rows().length).toBe(1);
    httpMock.expectNone(`${API}/scans/1`);
  });
});
