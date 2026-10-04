// Contratos TypeScript alineados 1:1 con los schemas Pydantic del backend.
// Los Decimal del backend llegan como string en JSON.

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  workspace_id: number;
  workspace_name: string;
}

export interface Product {
  id: number;
  barcode_raw: string;
  barcode_type: string | null;
  product_identifier: string | null;
  product_name: string | null;
  weight_value: string;
  weight_unit: 'KG' | 'LB';
  weight_kg: string;
  created_at: string;
}

export interface ScanRow {
  id: number;
  scanned_at: string;
  product_id: number;
  user_id: number;
  username: string;
  barcode_raw: string;
  product_name: string | null;
  weight_value: string;
  weight_unit: string;
  weight_kg: string;
  weight_lb: string;
}

// Espejo de app/schemas/product.py::ProductUpdate (todos opcionales:
// solo se envían los campos que se quieren modificar).
export interface ProductUpdate {
  barcode_raw?: string | null;
  barcode_type?: string | null;
  product_identifier?: string | null;
  product_name?: string | null;
  weight_value?: number | null;
  weight_unit?: 'KG' | 'LB' | null;
}

export type ScanStatus = 'existing' | 'created' | 'needs_weight';

export interface ScanResponse {
  status: ScanStatus;
  barcode: string;
  product: Product | null;
  scan: ScanRow | null;
}

export interface ScanPayload {
  barcode: string;
  weight_value?: number | null;
  weight_unit?: 'KG' | 'LB' | null;
  product_name?: string | null;
}
