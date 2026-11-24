import { enterContext } from './context.helpers';
import { chooseArticle, selectedArticle, suggestionResponse } from './article-picker.helpers';
import { test, expect } from '@playwright/test';

test('orientación, errores con foco y filtro local sin perder la referencia', async ({
  page,
}, info) => {
  const calls: string[] = [];
  await page.route('**/api/**', async (route) => {
    if (route.request().url().endsWith('/recomendar'))
      return route.fulfill({ json: suggestionResponse });
    const path = new URL(route.request().url()).pathname;
    calls.push(path);
    if (path.endsWith('/clasificadores')) await route.fulfill({ json: { clasificadores: [] } });
    else if (path.endsWith('/disponibilidad'))
      await route.fulfill({
        json: {
          version_contenido: 'v1',
          articulos: route
            .request()
            .postDataJSON()
            .paper_ids.map((paper_id: string) => ({ paper_id, disponible: true })),
        },
      });
    else await route.abort();
  });
  await page.goto('/');
  await expect(page.getByRole('navigation', { name: 'Pasos del análisis' })).toBeVisible();
  await expect(page.getByText('Pega el párrafo que contiene la cita.')).toBeVisible();
  const input = page.getByLabel('Contexto en inglés');
  await input.fill('As shown by the IBM models, alignment helps translation.');
  await expect(page.getByText(/No se detectó ninguna referencia/)).toBeVisible();
  await page.getByRole('button', { name: 'Usar selección', exact: true }).click();
  await expect(input).toBeFocused();
  await expect(input).toHaveAttribute('aria-invalid', 'true');
  await input.evaluate((field: HTMLTextAreaElement) => field.setSelectionRange(16, 26));
  await page.getByRole('button', { name: 'Usar selección', exact: true }).click();
  await expect(page.getByRole('radio', { name: 'IBM models' })).toBeChecked();
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeEnabled();
  await enterContext(page);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, 'W05-0821');
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }),
  ).toBeEnabled();
  const context = await page.getByLabel('Contexto en inglés').inputValue();
  await page.getByRole('button', { name: 'Cambiar artículo', exact: true }).click();
  const filter = page.getByRole('searchbox', { name: 'Buscar por título o ID', exact: true });
  const article = selectedArticle(page);
  await filter.fill('w05-0821');
  await expect(page.locator('.article-options > li')).toHaveCount(1);
  await expect(article).toContainText('W05-0821');
  await filter.fill('titulo-inexistente');
  await expect(page.getByText(/0 coincidencias/)).toBeVisible();
  await expect(article).toContainText('W05-0821');
  await filter.fill('translation');
  await expect(page.locator('.article-options > li')).toHaveCount(5);
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(context);
  expect(
    calls.every((path) => path.endsWith('/clasificadores') || path.endsWith('/disponibilidad')),
  ).toBe(true);
  await filter.fill('');
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
  await page.screenshot({ path: info.outputPath('flujo-preparado.png'), fullPage: true });
});

test('fallo del catálogo permite reintentar sin borrar el contexto', async ({ page }) => {
  await page.route('**/api/analisis-cita-ms/recomendar', (r) =>
    r.fulfill({ json: suggestionResponse }),
  );
  await page.route('**/api/analisis-cita-ms/disponibilidad', (route) =>
    route.fulfill({
      json: { version_contenido: 'v1', articulos: [{ paper_id: 'W05-0821', disponible: true }] },
    }),
  );
  let attempts = 0;
  let recovered = false;
  await page.route('**/api/clasificadores', async (route) => {
    attempts++;
    if (!recovered) await route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    else
      await route.fulfill({
        json: { clasificadores: [{ id: 'M' }, { id: 'S' }, { id: 'commercial' }] },
      });
  });
  await page.goto('/');
  await page
    .getByLabel('Contexto en inglés')
    .fill('Earlier research TARGETCIT provides the method.');
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, 'W05-0821');
  await chooseArticle(page, 'W05-0821');
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  await expect(
    page.getByText('No se pudo consultar el catálogo de clasificadores. Puedes usar M/S.'),
  ).toBeVisible();
  recovered = true;
  await page.getByRole('button', { name: 'Reintentar catálogo' }).click();
  await expect(page.locator('#classifier option[value="commercial"]')).toHaveCount(1);
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(
    'Earlier research TARGETCIT provides the method.',
  );
  expect(attempts).toBeGreaterThanOrEqual(2);
});
