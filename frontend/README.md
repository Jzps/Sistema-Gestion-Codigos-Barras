# Frontend — SGCBP (Angular 20)

SPA de la aplicación SGCBP. Sin librerías UI externas: SCSS propio y
componentes standalone.

## Comandos

```bash
npm install                # una sola vez
npm start                  # servidor de desarrollo en http://localhost:4200
npm run build              # build de verificación (configuración development)
npm run build:prod         # build de PRODUCCIÓN (exige la variable API_URL)
npm test                   # tests unitarios (Karma + Jasmine)
```

En Windows sin Chrome instalado, apunta Karma a Edge (Chromium):

```bash
CHROME_BIN='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' \
  npx ng test --watch=false --browsers=ChromeHeadless
```

## Entornos

| Fichero | Cuándo se usa | `apiUrl` |
| --- | --- | --- |
| `src/environments/environment.ts` | desarrollo (`ng serve`, `ng build`) | `http://localhost:8000/api` |
| `src/environments/environment.prod.ts` | producción (`ng build --configuration production`) | la definida por `API_URL` |

`angular.json` sustituye un fichero por otro en la configuración `production`
(`fileReplacements`). **El build de producción se hace siempre con
`npm run build:prod`** (`scripts/build-prod.mjs`), que:

1. exige la variable de entorno `API_URL` (URL de la API **sin** `/api`),
2. genera `environment.prod.ts` con esa URL,
3. compila,
4. comprueba que el bundle **no** contiene direcciones `localhost`.

```bash
API_URL=https://sgcbp-api.onrender.com npm run build:prod
```

El resultado se publica en `dist/frontend/browser`.

## Estructura

```text
src/app/
├── auth/       login, AuthService (sesión), guard, interceptor (withCredentials)
├── scanner/    pantalla principal: escaneo + alta de peso
├── products/   listado + edición inline + borrado con confirmación
├── history/    tabla de escaneos + borrado + exportación XLSX
├── dashboard/  panel de inicio
├── reports/    servicio de descarga del Excel
└── shared/     modelos TS, navbar, directiva de autofocus, api-error
```

Detalles de la arquitectura completa en `docs/architecture.md` (raíz del repo).
