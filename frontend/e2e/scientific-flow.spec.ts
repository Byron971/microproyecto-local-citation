import { chooseArticle, selectedArticle, suggestionResponse } from './article-picker.helpers';
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/clasificadores', (route) =>
    route.fulfill({ json: { clasificadores: [] } }),
  );
});

test('recorrido por artículo, selección de cita y resultados sin ranking ni JSON', async ({
  page,
}, testInfo) => {
  const calls: string[] = [];
  await page.route('**/api/**', async (route) => {
    if (route.request().url().endsWith('/recomendar'))
      return route.fulfill({ json: suggestionResponse });
    if (route.request().url().endsWith('/clasificadores')) {
      await route.fulfill({ json: { clasificadores: [] } });
      return;
    }
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/disponibilidad')) {
      await route.fulfill({
        json: {
          version_contenido: 'test-corpus',
          articulos: [{ paper_id: 'D15-1167', disponible: true }],
        },
      });
      return;
    }
    calls.push(path);
    expect(path).toBe('/api/analisis-cita-ms/articulo');
    const body = route.request().postDataJSON();
    expect(body).toEqual({
      asincrono: true,
      paper_id: 'D15-1167',
      contexto: 'Earlier work TARGETCIT and (Lee, 2019) introduced this method.',
    });
    const classifier = {
      clase: 'Application',
      probabilidad: 0.6,
      probabilidades: Array.from({ length: 9 }, (_, i) => ({
        clase: `Clase ${i}`,
        probabilidad: i ? 0.05 : 0.6,
      })),
    };
    await route.fulfill({
      json: {
        articulo: {
          paper_id: body.paper_id,
          titulo: 'Document Modeling',
          version_contenido: 'test-corpus',
          publicacion: 'https://aclanthology.org/D15-1167/',
        },
        top3: [1, 2, 3].map((i) => ({
          chunk_id: `p${i}`,
          texto: `Fragmento científico ${i}`,
          seccion: 'Methods',
          similitud_coseno: 0.5,
        })),
        clasificadores: { M: classifier, S: classifier },
        revision_scibert: 'abc123',
        tokens_ab: 512,
        dispositivo: 'cpu',
        aviso: 'Caso simulado de interfaz.',
      },
    });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Analizar una cita' })).toBeVisible();
  await expect(page.getByText('Explorar', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Resultados', { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeDisabled();
  expect(calls).toEqual([]);
  const input = page.getByLabel('Contexto en inglés');
  await input.fill('Earlier work [Smith, 2020] introduced this method.');
  const choice = page.getByRole('group', { name: 'Cita a analizar' });
  await expect(choice.getByRole('radio', { name: '[Smith, 2020]' })).toBeChecked();
  await input.fill('Earlier work [Smith, 2020] and (Lee, 2019) introduced this method.');
  await expect(choice.getByRole('radio')).toHaveCount(2);
  await expect(page.getByText('Elige la cita que quieres analizar', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeDisabled();
  await choice.getByRole('radio', { name: '[Smith, 2020]' }).check();
  await expect(input).toHaveValue(
    'Earlier work [Smith, 2020] and (Lee, 2019) introduced this method.',
  );
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, 'D15-1167');
  await expect(page.getByRole('link', { name: 'Abrir publicación' })).toHaveAttribute(
    'href',
    'https://aclanthology.org/D15-1167/',
  );
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  await page.getByLabel('Familia y modelo').selectOption('S');
  await page.getByRole('button', { name: 'Analizar cita', exact: true }).click();
  await expect(page.getByText('Fragmento científico 1')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Modelo S', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toHaveCount(0);
  expect(calls).toEqual(['/api/analisis-cita-ms/articulo']);
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath('scientific-flow.png'), fullPage: true });
  await page.getByRole('button', { name: 'Editar contexto', exact: true }).click();
  await input.fill('A changed context.');
  await expect(page.getByText('Fragmento científico 1')).toHaveCount(0);
});

for (const path of [
  '/datos',
  '/modelo',
  '/negativos',
  '/fragmentos',
  '/funcion',
  '/funcion-b',
  '/analisis-ms',
]) {
  test(`la ruta ${path} redirige al análisis`, async ({ page }) => {
    await page.goto(path);
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('heading', { name: 'Analizar una cita' })).toBeVisible();
    await expect(page.locator('input[type=file]')).toHaveCount(0);
  });
}

test('rechaza marcas múltiples y exceso de longitud antes de inferir', async ({ page }) => {
  const calls: string[] = [];
  await page.route('**/api/**', async (route) => {
    if (route.request().url().endsWith('/recomendar'))
      return route.fulfill({ json: suggestionResponse });
    if (route.request().url().endsWith('/clasificadores')) {
      await route.fulfill({ json: { clasificadores: [] } });
      return;
    }
    if (route.request().url().endsWith('/disponibilidad')) {
      await route.fulfill({
        json: {
          version_contenido: 'test-corpus',
          articulos: [{ paper_id: 'D15-1167', disponible: true }],
        },
      });
      return;
    }
    calls.push(route.request().url());
    await route.abort();
  });
  await page.goto('/');
  const input = page.getByLabel('Contexto en inglés');
  await input.fill('Earlier work TARGETCIT and TARGETCIT.');
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeDisabled();
  await expect(page.getByText('Hay varias marcas: deja solo una')).toBeVisible();
  await input.fill('x'.repeat(4000) + ' TARGETCIT');
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeDisabled();
  await expect(page.locator('#context-state')).toContainText((4010).toLocaleString('es'));
  expect(calls).toEqual([]);
});
