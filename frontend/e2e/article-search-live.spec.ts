import { test, expect } from '@playwright/test';
import { selectedArticle } from './article-picker.helpers';

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
  expect(data.total_catalogo).toBe(37);
  await expect(page.getByRole('heading', { name: 'Sugeridos según tu contexto' })).toBeVisible();
  await expect(selectedArticle(page)).toHaveCount(0);
  await page.screenshot({ path: info.outputPath('sugerencias-reales.png'), fullPage: true });
  await page
    .getByRole('button', { name: /Seleccionar artículo:/ })
    .first()
    .click();
  await expect(selectedArticle(page)).toContainText(data.recomendaciones[0].paper_id);
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await page.getByRole('button', { name: 'Siguiente: clasificador' }).click();
  await expect(page.getByLabel('Clasificador', { exact: true })).toBeVisible();
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
});
