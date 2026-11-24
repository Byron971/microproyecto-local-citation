import { enterContext } from './context.helpers';
import { test, expect, type Page } from '@playwright/test';
import catalog from '../src/articleCatalog.json' with { type: 'json' };
import { chooseArticle, suggestionResponse } from './article-picker.helpers';
import { JOB_ID, isAnalysisRead, isAnalysisStart, job } from './analysis-job.helpers';

const classifier = {
  clase: 'Application',
  probabilidad: 0.6,
  probabilidades: Array.from({ length: 9 }, (_, i) => ({
    clase: `Clase ${i}`,
    probabilidad: i ? 0.05 : 0.6,
  })),
};
const resultado = {
  articulo: {
    paper_id: 'W05-0821',
    titulo: 'Article',
    version_contenido: catalog.version_contenido,
  },
  top3: [1, 2, 3].map((i) => ({
    chunk_id: `p${i}`,
    texto: `Fragmento ${i}`,
    seccion: 'Methods',
    similitud_coseno: 0.5,
  })),
  clasificadores: { M: classifier, S: classifier },
  tokens_ab: 512,
  dispositivo: 'cpu',
};
const labels = classifier.probabilidades.map((p) => p.clase);

type Mock = {
  starts: { clave_idempotencia: string }[];
  reads: number;
  cancels: number;
  commercial: number;
  // Estado devuelto por cada GET; el último se repite.
  states: Record<string, unknown>[];
  cancelStatus?: number;
};

async function mockApi(page: Page, mock: Mock, commercial = false) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/clasificadores'))
      return route.fulfill({
        json: { clasificadores: commercial ? [{ id: 'M' }, { id: 'commercial' }] : [] },
      });
    if (path.endsWith('/recomendar')) return route.fulfill({ json: suggestionResponse });
    if (path.endsWith('/disponibilidad'))
      return route.fulfill({
        json: {
          version_contenido: catalog.version_contenido,
          articulos: [{ paper_id: 'W05-0821', disponible: true }],
        },
      });
    if (isAnalysisStart(path)) {
      expect(request.method()).toBe('POST');
      mock.starts.push(request.postDataJSON());
      return route.fulfill({ status: 202, json: job('en_cola') });
    }
    if (path.endsWith(`/trabajos/${JOB_ID}/cancelar`)) {
      mock.cancels++;
      if (mock.cancelStatus)
        return route.fulfill({
          status: mock.cancelStatus,
          json: { detail: 'El análisis ya se está calculando y no se puede detener.' },
        });
      return route.fulfill({ json: job('cancelado') });
    }
    if (isAnalysisRead(path)) {
      expect(request.method()).toBe('GET');
      const state = mock.states[Math.min(mock.reads, mock.states.length - 1)];
      mock.reads++;
      return route.fulfill({ json: state });
    }
    if (path.endsWith('/comercial/clasificar')) {
      mock.commercial++;
      return route.fulfill({
        json: {
          paper_id: 'W05-0821',
          version_contenido: catalog.version_contenido,
          modelo_solicitado: 'gpt-6.1-sol',
          modelo_efectivo: 'gpt-6.1-sol',
          clase: 'Application',
          puntuaciones: labels.map((clase) => ({ clase, valor: 0.1 })),
        },
      });
    }
    throw new Error(`Ruta inesperada ${path}`);
  });
}

const newMock = (states: Record<string, unknown>[], extra: Partial<Mock> = {}): Mock => ({
  starts: [],
  reads: 0,
  cancels: 0,
  commercial: 0,
  states,
  ...extra,
});

async function startAnalysis(page: Page, variant?: string) {
  await page.goto('/');
  await enterContext(page);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, 'W05-0821');
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  if (variant) {
    await page.getByLabel('Familia y modelo').selectOption(variant);
    await page.getByRole('checkbox', { name: /Acepto enviar/ }).check();
  }
  await page.getByRole('button', { name: 'Ver resultados', exact: true }).dblclick();
}

const status = (page: Page) => page.locator('.results-loading[role="status"]');

test('cola, cálculo y resultado con un único POST', async ({ page }, testInfo) => {
  const mock = newMock([
    job('en_cola'),
    job('procesando'),
    job('procesando'),
    job('completado', { resultado }),
  ]);
  await mockApi(page, mock);
  await startAnalysis(page);
  await expect(status(page)).toContainText('En cola');
  await expect(status(page)).toContainText('Hay otro análisis en curso');
  await expect(page.getByRole('button', { name: 'Cancelar análisis' })).toBeVisible();
  // Sin porcentajes, posiciones ni tiempos restantes inventados mientras espera.
  await expect(status(page)).not.toContainText(/%|posición|restante|\d+ s/i);
  await page.screenshot({ path: testInfo.outputPath('cola.png'), fullPage: true });
  await expect(status(page)).toContainText('Calculando los resultados…', { timeout: 8000 });
  await expect(page.getByRole('button', { name: 'Cancelar análisis' })).toHaveCount(0);
  await expect(status(page)).not.toContainText(/%|posición|restante|\d+ s/i);
  await page.screenshot({ path: testInfo.outputPath('procesando.png'), fullPage: true });
  await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toBeVisible({
    timeout: 12000,
  });
  expect(mock.starts).toHaveLength(1); // Doble clic: una sola admisión.
  expect(mock.starts[0].clave_idempotencia).toMatch(/^[A-Za-z0-9-]{16,64}$/);
});

test('recargar retoma el mismo trabajo sin otro POST', async ({ page }) => {
  const mock = newMock([job('procesando')]);
  await mockApi(page, mock);
  await startAnalysis(page);
  await expect(status(page)).toContainText('Calculando los resultados…', { timeout: 8000 });
  mock.states = [job('completado', { resultado })];
  mock.reads = 0;
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toBeVisible();
  await expect(page.locator('#workflow-step-3')).toHaveAttribute('aria-current', 'step');
  expect(mock.starts).toHaveLength(1);
  // El contexto y el artículo se recuperan: se puede volver a editar.
  await page.getByRole('button', { name: 'Editar contexto', exact: true }).click();
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(/language modeling approach/);
  // Editar invalida el seguimiento: otra recarga ya no retoma el trabajo.
  await page.getByLabel('Contexto en inglés').fill('Edited context [1] for a new analysis.');
  await page.reload();
  await expect(page.locator('#workflow-step-0')).toHaveAttribute('aria-current', 'step');
  expect(mock.starts).toHaveLength(1);
});

for (const [estado, mensaje] of [
  ['fallido', 'El servicio se reinició durante el cálculo'],
  ['expirado', 'esperó demasiado en la cola'],
] as const) {
  test(`${estado}: mensaje útil, datos conservados y reintento explícito`, async ({ page }) => {
    const mock = newMock([
      job(estado, { error: { codigo: estado === 'fallido' ? 'reinicio' : 'expirado', mensaje } }),
    ]);
    await mockApi(page, mock);
    await startAnalysis(page);
    await expect(page.getByRole('alert')).toContainText(mensaje, { timeout: 8000 });
    await expect(page.locator('#analysis-error')).toBeFocused();
    expect(mock.starts).toHaveLength(1);
    mock.states = [job('completado', { resultado })];
    mock.reads = 0;
    await page.getByRole('button', { name: 'Volver a intentar', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toBeVisible({
      timeout: 8000,
    });
    expect(mock.starts).toHaveLength(2);
    expect(mock.starts[1].clave_idempotencia).not.toBe(mock.starts[0].clave_idempotencia);
  });
}

test('cancelar mientras espera en cola', async ({ page }) => {
  const mock = newMock([job('en_cola')]);
  await mockApi(page, mock);
  await startAnalysis(page);
  await page.getByRole('button', { name: 'Cancelar análisis' }).click();
  await expect(page.getByText('Cancelación registrada')).toBeVisible();
  mock.states = [job('cancelado')];
  await expect(page.getByRole('alert')).toContainText('Cancelaste el análisis', { timeout: 8000 });
  expect(mock.cancels).toBe(1);
  expect(mock.starts).toHaveLength(1);
});

test('si ya empezó el cálculo, cancelar lo explica y no lo detiene', async ({ page }) => {
  const mock = newMock([job('en_cola')], { cancelStatus: 409 });
  await mockApi(page, mock);
  await startAnalysis(page);
  await page.getByRole('button', { name: 'Cancelar análisis' }).click();
  await expect(page.getByText('no se puede detener')).toBeVisible();
  mock.states = [job('completado', { resultado })];
  await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toBeVisible({
    timeout: 8000,
  });
});

test('recargar no repite la llamada comercial', async ({ page }) => {
  const mock = newMock([job('completado', { resultado })]);
  await mockApi(page, mock, true);
  await startAnalysis(page, 'commercial');
  await expect(page.getByRole('region', { name: 'Clasificación comercial' })).toBeVisible({
    timeout: 8000,
  });
  expect(mock.commercial).toBe(1);
  await page.reload();
  await expect(page.locator('#fragment-1').getByText('Fragmento 1', { exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('no se repitió al recargar');
  expect(mock.commercial).toBe(1);
  expect(mock.starts).toHaveLength(1);
});
