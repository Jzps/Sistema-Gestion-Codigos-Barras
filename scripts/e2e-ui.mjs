/**
 * SGCBP — Verificación E2E de la UI (sin dependencias externas).
 *
 * Usa Edge headless (Chromium) vía DevTools Protocol (CDP) con el WebSocket
 * nativo de Node 22. Conduce la aplicación real servida en :4200 contra la
 * API real en :8000: login, escaneo, edición, borrados y consistencia.
 *
 * Requisitos: `./start.sh` en marcha (API :8000 + Angular :4200).
 * Uso:        node scripts/e2e-ui.mjs
 */
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const APP = 'http://localhost:4200';
const API = 'http://localhost:8000/api';
const DEBUG_PORT = 9222;

const results = [];
function check(name, cond, extra = '') {
  results.push([name, !!cond]);
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : '  ' + extra}`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ------------------------------- CDP client -------------------------------
let msgId = 0;
const pending = new Map();
let ws;

function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function js(expression) {
  const res = await cdp('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (res.exceptionDetails) {
    throw new Error('JS error: ' + JSON.stringify(res.exceptionDetails).slice(0, 400));
  }
  return res.result?.value;
}

async function waitFor(description, expression, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      if (await js(expression)) return true;
    } catch {
      /* página aún cargando */
    }
    await sleep(250);
  }
  throw new Error(`Timeout esperando: ${description}`);
}

// Helpers ejecutados DENTRO de la página (simulan al usuario real).
const PAGE_HELPERS = `
window.__e2e = {
  setValue(sel, value) {
    const el = document.querySelector(sel);
    if (!el) throw new Error('no existe ' + sel);
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  },
  clickButton(text) {
    const btn = [...document.querySelectorAll('button')]
      .find(b => b.textContent.trim().startsWith(text) && !b.disabled);
    if (!btn) throw new Error('no existe botón ' + text);
    btn.click();
  },
  clickRowButton(cellText, btnText) {
    // Coincidencia EXACTA de celda: 'E2E-1-B' no debe casar con 'E2E-1'.
    const row = [...document.querySelectorAll('tbody tr')].find(tr =>
      [...tr.querySelectorAll('td')].some(td => td.textContent.trim() === cellText));
    if (!row) throw new Error('no existe fila con celda exacta ' + cellText);
    const btn = [...row.querySelectorAll('button')]
      .find(b => b.textContent.trim().startsWith(btnText));
    if (!btn) throw new Error('no existe botón ' + btnText + ' en fila ' + cellText);
    btn.click();
  },
  rowsWithCell(cellText) {
    return [...document.querySelectorAll('tbody tr')].filter(tr =>
      [...tr.querySelectorAll('td')].some(td => td.textContent.trim() === cellText)).length;
  },
  activeId() {
    const el = document.activeElement;
    return el ? (el.id || el.tagName) : null;
  },
  inputValue(sel) {
    const el = document.querySelector(sel);
    return el ? el.value : null;
  },
  bodyText() { return document.body.innerText; },
  pressEnter(sel) {
    const el = document.querySelector(sel);
    if (!el) throw new Error('no existe ' + sel);
    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  }
};`;

async function navigate(url) {
  await cdp('Page.navigate', { url });
  await waitFor(`carga de ${url}`, `document.readyState === 'complete'`);
  await js(PAGE_HELPERS); // reinstala helpers tras cada navegación
}

const bodyIncludes = (text) =>
  `window.__e2e && window.__e2e.bodyText().includes(${JSON.stringify(text)})`;

// --------------------------------- main -----------------------------------
async function main() {
  // API viva es prerrequisito.
  const health = await fetch(`${API}/health`).then((r) => r.json()).catch(() => null);
  if (!health || health.status !== 'ok') {
    throw new Error('La API no responde en :8000. Ejecuta ./start.sh primero.');
  }

  // Códigos de la prueba. Se declaran aqui (fuera del try) porque la
  // limpieza del bloque finally los necesita para borrar todo lo creado.
  const code = `E2E-${Date.now() % 1000000}`;
  const otherCode = `${code}-B`;
  const nameEdited = 'E2E Corregido';
  console.log(`Código de prueba: ${code}`);

  const profile = mkdtempSync(join(tmpdir(), 'sgcbp-e2e-'));
  const edge = spawn(EDGE, [
    '--headless=new',
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    'about:blank',
  ]);

  try {
    // Esperar a que el endpoint de depuración esté listo.
    let version = null;
    for (let i = 0; i < 40 && !version; i++) {
      version = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`).catch(() => null);
      if (version) version = await version.json();
      else await sleep(250);
    }
    if (!version) throw new Error('Edge headless no expuso CDP');

    // Abrir pestaña nueva y conectar al WebSocket de depuración.
    const target = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/new?about:blank`, {
      method: 'PUT',
    }).then((r) => r.json());

    ws = new WebSocket(target.webSocketDebuggerUrl);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id);
        pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      }
    };
    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.onerror = rej;
    });
    await cdp('Page.enable');
    await cdp('Runtime.enable');

    // -- 1. Login desde la UI ------------------------------------------------
    await navigate(APP);
    await waitFor('formulario de login', `!!document.querySelector('input[name="username"]')`);
    await js(`__e2e.setValue('input[name="username"]', 'admin')`);
    await js(`__e2e.setValue('input[name="password"]', 'admin123')`);
    await js(`__e2e.clickButton('Iniciar sesión')`);
    await waitFor('redirección al panel', `location.pathname === '/'`);
    check('login desde la UI llega al panel', true);

    // -- 2. Escanear código nuevo + alta de peso en LB -----------------------
    await navigate(`${APP}/escanear`);
    await waitFor('input de escaneo', `!!document.querySelector('#barcode')`);
    await js(`__e2e.setValue('#barcode', '${code}')`);
    await js(`__e2e.pressEnter('#barcode')`);
    await waitFor('pide peso (producto nuevo)', bodyIncludes('Producto no registrado'));

    // -- 2b. El foco NUNCA debe saltar al campo de peso ----------------------
    //     El lector USB escribe en el elemento que tiene el foco. Si el foco
    //     estuviera en #weight, el siguiente codigo de barras se guardaria
    //     como PESO del producto pendiente (corrupcion silenciosa de datos).
    await sleep(600);
    const focusedId = await js(`__e2e.activeId()`);
    check(
      'con el formulario de peso abierto el foco sigue en el campo de codigo',
      focusedId === 'barcode',
      `foco real: ${focusedId}`,
    );

    // Simula la entrada de un lector USB (teclado) con el formulario abierto.
    await cdp('Input.insertText', { text: '7501234567890' });
    await sleep(300);
    const weightValue = await js(`__e2e.inputValue('#weight')`);
    const barcodeValue = await js(`__e2e.inputValue('#barcode')`);
    check(
      'un escaneo con el formulario de peso abierto NO acaba en el campo de peso',
      String(weightValue).trim() === '',
      `valor real en #weight: "${weightValue}"`,
    );
    check(
      'el escaneo con el formulario abierto va al campo de codigo',
      String(barcodeValue).trim() === '7501234567890',
      `valor real en #barcode: "${barcodeValue}"`,
    );
    // Limpiar el campo de codigo: el flujo sigue con el alta de peso.
    await js(`__e2e.setValue('#barcode', '')`);

    await js(`__e2e.setValue('#weight', '44.09')`);
    await js(`__e2e.setValue('#unit', 'LB')`);
    await js(`__e2e.clickButton('Guardar y registrar')`);
    await waitFor('confirmación de alta', bodyIncludes('Nuevo producto registrado'));
    check('escaneo de código nuevo pide peso y crea el producto', true);

    // -- 3. Re-escanear: reutiliza el peso ------------------------------------
    await js(`__e2e.setValue('#barcode', '${code}')`);
    await js(`__e2e.pressEnter('#barcode')`);
    await waitFor('producto existente', bodyIncludes('Producto existente'));
    check('segundo escaneo recupera el peso sin pedirlo', true);

    // -- 4. Productos: editar nombre ------------------------------------------
    await navigate(`${APP}/productos`);
    await waitFor('fila del producto', bodyIncludes(code));
    await js(`__e2e.clickRowButton('${code}', 'Editar')`);
    await waitFor('formulario de edición', bodyIncludes('Editar producto'));
    await js(`__e2e.setValue('#editName', '${nameEdited}')`);
    await js(`__e2e.clickButton('Guardar cambios')`);
    await waitFor('fila actualizada', bodyIncludes(nameEdited));
    check('editar nombre en Productos se guarda y se ve al instante', true);

    // -- 5. Barcode duplicado -> 409 visible ----------------------------------
    //    (se crea un segundo producto vía API usando la sesión del navegador)
    await js(`fetch('${API}/scans', {method:'POST', credentials:'include',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({barcode:'${otherCode}', weight_value:5, weight_unit:'KG'})})`);
    await navigate(`${APP}/productos`);
    await waitFor('fila del producto tras recargar', bodyIncludes(code));
    await js(`__e2e.clickRowButton('${code}', 'Editar')`);
    await waitFor('formulario de edición', bodyIncludes('Editar producto'));
    await js(`__e2e.setValue('#editBarcode', '${otherCode}')`);
    await js(`__e2e.clickButton('Guardar cambios')`);
    await waitFor('error 409 visible', bodyIncludes('Ya existe un producto'));
    check('barcode duplicado muestra error 409 comprensible', true);
    await js(`__e2e.clickButton('Cancelar')`);
    await waitFor('edición cerrada', `!(${bodyIncludes('Editar producto')})`);

    // -- 6. Eliminar producto CON scans -> 409 y sigue en la tabla ------------
    await js(`__e2e.clickRowButton('${code}', 'Eliminar')`);
    await waitFor('confirmación de borrado', bodyIncludes('¿Seguro que deseas eliminar'));
    await js(`__e2e.clickButton('Sí, eliminar')`);
    await waitFor('error 409 por tener escaneos', bodyIncludes('escaneo(s)'));
    const stillThere = await js(bodyIncludes(code));
    check('eliminar producto con scans muestra 409 y el producto permanece', stillThere);

    // -- 7. Escanear tras editar: usa datos actualizados ----------------------
    await navigate(`${APP}/escanear`);
    await waitFor('input de escaneo', `!!document.querySelector('#barcode')`);
    await js(`__e2e.setValue('#barcode', '${code}')`);
    await js(`__e2e.pressEnter('#barcode')`);
    await waitFor('resultado con nombre corregido', bodyIncludes(nameEdited));
    check('escanear tras editar usa los datos actualizados del producto', true);

    // -- 8. Historial: eliminar todos los scans del producto ------------------
    await navigate(`${APP}/historial`);
    await waitFor('historial cargado', bodyIncludes(code));
    for (let i = 0; i < 3; i++) {
      const count = await js(`__e2e.rowsWithCell('${code}')`);
      if (count === 0) break;
      await js(`__e2e.clickRowButton('${code}', 'Eliminar')`);
      await waitFor('confirmación de borrado', bodyIncludes('¿Seguro que deseas eliminar'));
      await js(`__e2e.clickButton('Sí, eliminar')`);
      await waitFor('fila eliminada del historial', `__e2e.rowsWithCell('${code}') === ${count - 1}`);
    }
    const remaining = await js(`__e2e.rowsWithCell('${code}')`);
    check('todos los scans del producto eliminados desde Historial', remaining === 0);

    // -- 9. Producto sigue existiendo y ahora SÍ se puede eliminar ------------
    await navigate(`${APP}/productos`);
    await waitFor('producto aún visible', bodyIncludes(code));
    await js(`__e2e.clickRowButton('${code}', 'Eliminar')`);
    await waitFor('confirmación de borrado', bodyIncludes('¿Seguro que deseas eliminar'));
    await js(`__e2e.clickButton('Sí, eliminar')`);
    await waitFor('producto eliminado de la tabla', `__e2e.rowsWithCell('${code}') === 0`);
    check('producto sin scans se elimina y desaparece de Productos', true);

    // -- 10. Layout en ventana estrecha (480px): sin scroll horizontal --------
    await cdp('Emulation.setDeviceMetricsOverride', {
      width: 480,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false,
    });
    for (const page of ['productos', 'historial']) {
      await navigate(`${APP}/${page}`);
      await sleep(600);
      const overflow = await js(
        `document.documentElement.scrollWidth - document.documentElement.clientWidth`,
      );
      check(`layout de /${page} no se rompe a 480px (overflow-x: ${overflow}px)`, overflow <= 2);
    }
    await cdp('Emulation.clearDeviceMetricsOverride');
  } finally {
    // -- Limpieza determinista (se ejecuta SIEMPRE, incluso si un check falla).
    //     Se borra por API con la sesion del navegador: es fiable y no depende
    //     de la paginacion de la UI. Antes esta limpieza era incompleta y
    //     dejaba productos "E2E-*-B" huerfanos en la base de datos.
    try {
      const leftover = await js(`(async () => {
        const codes = ${JSON.stringify([code, otherCode])};
        const del = async (url) => {
          try { await fetch(url, { method: 'DELETE', credentials: 'include' }); } catch (e) {}
        };
        const get = async (url) => {
          const r = await fetch(url, { credentials: 'include' });
          return r.ok ? await r.json() : [];
        };
        const scans = await get('${API}/scans?limit=1000');
        for (const s of scans) if (codes.includes(s.barcode_raw)) await del('${API}/scans/' + s.id);
        const products = await get('${API}/products?limit=1000');
        for (const p of products) if (codes.includes(p.barcode_raw)) await del('${API}/products/' + p.id);
        const scansLeft = (await get('${API}/scans?limit=1000')).filter((s) => codes.includes(s.barcode_raw));
        const productsLeft = (await get('${API}/products?limit=1000')).filter((p) => codes.includes(p.barcode_raw));
        return { scans: scansLeft.length, products: productsLeft.length };
      })()`);
      check(
        'la prueba no deja registros basura en la base de datos',
        leftover.scans === 0 && leftover.products === 0,
        `scans=${leftover.scans} products=${leftover.products}`,
      );
    } catch (err) {
      check('la prueba no deja registros basura en la base de datos', false, err.message);
    }

    try {
      ws?.close();
    } catch {}
    edge.kill();
    await sleep(500);
    spawn('taskkill', ['/PID', String(edge.pid), '/T', '/F'], { stdio: 'ignore' });
    rmSync(profile, { recursive: true, force: true });
  }

  const failed = results.filter(([, ok]) => !ok);
  console.log(`\n${results.length - failed.length}/${results.length} comprobaciones E2E superadas`);
  if (failed.length > 0) process.exit(1);
}

main().catch((err) => {
  console.error('E2E abortado:', err.message);
  process.exit(1);
});
