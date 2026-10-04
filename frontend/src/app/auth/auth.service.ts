import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, catchError, map, of, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { User } from '../shared/models';

/**
 * Estado de sesión del lado del cliente.
 * El token JWT vive en una cookie HttpOnly: este servicio nunca lo ve ni lo
 * guarda; solo consulta al backend quién es el usuario actual.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  readonly user = signal<User | null>(null);
  /** true una vez que se ha consultado /auth/me al menos una vez. */
  readonly loaded = signal(false);

  login(username: string, password: string): Observable<User> {
    return this.http
      .post<{ user: User }>(`${this.api}/auth/login`, { username, password })
      .pipe(
        map((res) => res.user),
        tap((user) => {
          this.user.set(user);
          this.loaded.set(true);
        }),
      );
  }

  logout(): Observable<void> {
    return this.http.post<void>(`${this.api}/auth/logout`, {}).pipe(
      tap(() => this.user.set(null)),
    );
  }

  /** Carga el usuario actual. Nunca lanza: devuelve null si no hay sesión. */
  loadMe(): Observable<User | null> {
    return this.http.get<User>(`${this.api}/auth/me`).pipe(
      tap((user) => {
        this.user.set(user);
        this.loaded.set(true);
      }),
      catchError(() => {
        this.user.set(null);
        this.loaded.set(true);
        return of(null);
      }),
    );
  }

  /** Devuelve el usuario en caché o lo consulta la primera vez. */
  ensureLoaded(): Observable<User | null> {
    return this.loaded() ? of(this.user()) : this.loadMe();
  }
}
