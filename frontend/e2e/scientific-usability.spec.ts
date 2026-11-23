import { test, expect } from '@playwright/test';

test('orientación, errores con foco y filtro local sin perder la referencia', async ({
  page,
}, info) => {
  const calls: string[] = [];
  await page.route('**/api/**', async (route) => {
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
  await expect(page.getByText('Añade el contexto y marca una sola cita.')).toBeVisible();
  await page.getByRole('button', { name: 'Marcar cita', exact: true }).click();
  await expect(page.getByLabel('Contexto en inglés')).toBeFocused();
  await expect(page.getByLabel('Contexto en inglés')).toHaveAttribute('aria-invalid', 'true');
  await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await expect(page.getByText('Artículo disponible. Continúa con el clasificador.')).toBeVisible();
  const context = await page.getByLabel('Contexto en inglés').inputValue();
  const filter = page.getByRole('searchbox', { name: 'Filtrar artículos por título o ID' });
  const article = page.getByLabel('Artículo preparado por título e ID');
  await filter.fill('w05-0821');
  await expect(article.locator('option')).toHaveCount(2);
  await expect(article).toHaveValue('W05-0821');
  await filter.fill('titulo-inexistente');
  await expect(page.getByText(/0 coincidencias/)).toBeVisible();
  await expect(article).toHaveValue('W05-0821');
  await filter.fill('translation');
  await expect(article.locator('option')).not.toHaveCount(2);
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
  await page.getByLabel('Artículo preparado por título e ID').selectOption('W05-0821');
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
