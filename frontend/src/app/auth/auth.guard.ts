import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';

import { AuthService } from './auth.service';

/** Rutas privadas: exige sesión. El backend vuelve a validar en cada llamada. */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureLoaded()
    .pipe(map((user) => (user ? true : router.createUrlTree(['/login']))));
};

/** /login: si ya hay sesión, redirige a la aplicación. */
export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureLoaded()
    .pipe(map((user) => (user ? router.createUrlTree(['/']) : true)));
};
