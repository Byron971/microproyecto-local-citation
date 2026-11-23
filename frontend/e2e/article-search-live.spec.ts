import { test, expect } from '@playwright/test';
import fullCatalog from '../src/fullArticleCatalog.json' with { type: 'json' };
import prepared from '../src/articleCatalog.json' with { type: 'json' };
import { chooseArticle, selectedArticle } from './article-picker.helpers';

test.skip(!process.env.LIVE_ARTICLE_SEARCH, 'Requiere servicio científico público.');
test('sugerir artículos reales y confirmar uno sin ejecutar clasificación', async ({
  page,
}, info) => {
  test.setTimeout(90000);
  await page.goto('/');
  await page
    .getByLabel('Contexto en inglés')
    .fill(
      'We use the language modeling approach described in TARGETCIT to improve a statistical machine translation system.',
    );
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith('/api/analisis-cita-ms/recomendar'),
    { timeout: 60000 },
  );
  await page.getByRole('button', { name: 'Sugerir según mi contexto' }).click();
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
  await page.screenshot({ path: info.outputPath('sugerencias-reales.png'), fullPage: true });
  await page
    .getByRole('button', { name: /Seleccionar artículo:/ })
    .first()
    .click();
  await expect(selectedArticle(page)).toContainText(data.recomendaciones[0].paper_id);
  if (!prepared.articulos.some((a) => a.paper_id === data.recomendaciones[0].paper_id)) {
    await expect(page.getByText(/Este artículo no tiene texto preparado/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeDisabled();
    await chooseArticle(page, 'W05-0821');
  }
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await page.getByRole('button', { name: 'Siguiente: clasificador' }).click();
  await expect(page.getByLabel('Familia y modelo', { exact: true })).toBeVisible();
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
});
