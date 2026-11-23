import fs from 'node:fs';
import { test, expect } from '@playwright/test';
import fullCatalog from '../src/fullArticleCatalog.json' with { type: 'json' };
import prepared from '../src/articleCatalog.json' with { type: 'json' };
import { chooseArticle, selectedArticle } from './article-picker.helpers';

test.skip(!process.env.LIVE_ARTICLE_SEARCH, 'Requiere servicio científico público.');
test('sugerir artículos reales y confirmar uno sin ejecutar clasificación', async ({
  page,
}, info) => {
  test.setTimeout(90000);
  let suggestions = 0;
  let analyses = 0;
  page.on('request', (request) => {
    if (request.url().endsWith('/api/analisis-cita-ms/recomendar')) suggestions++;
    if (
      request.url().includes('/api/analisis-cita-ms/trabajos') ||
      request.url().endsWith('/api/comercial/clasificar')
    )
      analyses++;
  });
  await page.goto('/');
  await page
    .getByLabel('Contexto en inglés')
    .fill(
      'We use the language modeling approach described in TARGETCIT to improve a statistical machine translation system.',
    );
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith('/api/analisis-cita-ms/recomendar'),
    { timeout: 60000 },
  );
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const data = await response.json();
  expect(data.total_catalogo).toBe(19776);
  expect(data.version_catalogo).toBe(fullCatalog.source_sha256);
  expect(data.version_contenido).toBe(prepared.version_contenido);
  const known = new Set(fullCatalog.articulos.map((a) => a.paper_id));
  expect(data.recomendaciones).toHaveLength(5);
  expect(new Set(data.recomendaciones.map((a: { paper_id: string }) => a.paper_id)).size).toBe(5);
  expect(data.recomendaciones.every((a: { paper_id: string }) => known.has(a.paper_id))).toBe(true);
  await expect(page.getByRole('heading', { name: 'Sugeridos según tu contexto' })).toBeVisible();
  await expect(selectedArticle(page)).toHaveCount(0);
  expect(suggestions).toBe(1);
  await expect(page.getByRole('button', { name: 'Sugerir según mi contexto' })).toHaveCount(0);
  const source = JSON.parse(fs.readFileSync('../artifacts/scientific_search/papers.json', 'utf8'));
  for (const candidate of data.recomendaciones) {
    const original = source.find((a: { paper_id: string }) => a.paper_id === candidate.paper_id);
    expect(candidate.titulo).toBe(original.titulo);
    expect(candidate.resumen).toBe(original.resumen);
  }
  fs.writeFileSync(
    info.outputPath('sugerencias-reales.json'),
    JSON.stringify(
      {
        ...data,
        metadatos_contrastados: true,
        sugerencia_automatica: true,
        seleccion_manual_requerida: true,
      },
      null,
      2,
    ),
  );
  await page.screenshot({ path: info.outputPath('sugerencias-reales.png'), fullPage: true });
  await page
    .getByRole('button', { name: /Seleccionar artículo:/ })
    .first()
    .click();
  await expect(selectedArticle(page)).toContainText(data.recomendaciones[0].paper_id);
  if (
    !fullCatalog.articulos.find((a) => a.paper_id === data.recomendaciones[0].paper_id)?.preparado
  ) {
    await expect(page.getByText(/Este artículo no tiene texto preparado/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeDisabled();
    await chooseArticle(page, 'W05-0821');
  }
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await page.getByRole('button', { name: 'Siguiente: clasificador' }).click();
  await expect(page.getByLabel('Familia y modelo', { exact: true })).toBeVisible();
  expect(suggestions).toBe(1);
  expect(analyses).toBe(0);
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
});

test('buscar un artículo sin cobertura muestra su disponibilidad real', async ({ page }, info) => {
  const article = fullCatalog.articulos.find(
    (a) => !a.preparado && /^[A-Z][0-9]{2}-[0-9]{4}$/.test(a.paper_id),
  )!;
  await page.goto('/');
  await page
    .getByLabel('Contexto en inglés')
    .fill('Prior work TARGETCIT improves scientific methods.');
  const suggestions = page.waitForResponse((r) =>
    r.url().endsWith('/api/analisis-cita-ms/recomendar'),
  );
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  expect((await suggestions).status()).toBe(200);
  await chooseArticle(page, article.paper_id);
  await expect(page.getByText(/Este artículo no tiene texto preparado/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeDisabled();
  await expect(selectedArticle(page).getByRole('heading')).toBeFocused();
  await page.screenshot({ path: info.outputPath('catalogo-completo-publico.png'), fullPage: true });
});
