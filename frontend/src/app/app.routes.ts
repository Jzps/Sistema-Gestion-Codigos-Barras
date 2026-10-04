import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './auth/auth.guard';
import { Login } from './auth/login';
import { Dashboard } from './dashboard/dashboard';
import { History } from './history/history';
import { Products } from './products/products';
import { Scanner } from './scanner/scanner';

export const routes: Routes = [
  { path: 'login', component: Login, canActivate: [guestGuard] },
  { path: '', component: Dashboard, canActivate: [authGuard] },
  { path: 'escanear', component: Scanner, canActivate: [authGuard] },
  { path: 'historial', component: History, canActivate: [authGuard] },
  { path: 'productos', component: Products, canActivate: [authGuard] },
  { path: '**', redirectTo: '' },
];
