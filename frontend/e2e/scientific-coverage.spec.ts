import { chooseArticle, selectedArticle, suggestionResponse } from './article-picker.helpers';
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/analisis-cita-ms/recomendar', (r) =>
    r.fulfill({ json: suggestionResponse }),
  );
  await page.route('**/api/clasificadores', (route) =>
    route.fulfill({ json: { clasificadores: [] } }),
  );
});

for (const mode of ['missing', 'error', 'invalid'] as const) {
  test(`cobertura ${mode}: conserva contexto y referencia sin inferencia`, async ({ page }) => {
    let analyses = 0;
    let retry = false;
    await page.route('**/api/**', async (route) => {
      if (route.request().url().endsWith('/recomendar'))
        return route.fulfill({ json: suggestionResponse });
      if (route.request().url().endsWith('/clasificadores')) {
        await route.fulfill({ json: { clasificadores: [] } });
        return;
      }
      const request = route.request();
      if (!request.url().endsWith('/disponibilidad')) {
        analyses++;
        await route.abort();
        return;
      }
      const id = request.postDataJSON().paper_ids[0];
      if (retry) {
        await route.fulfill({
          json: { version_contenido: 'v1', articulos: [{ paper_id: id, disponible: true }] },
        });
        return;
      }
      if (mode === 'error')
        await route.fulfill({ status: 503, json: { detail: 'Service unavailable' } });
      else
        await route.fulfill({
          json: {
            version_contenido: 'v1',
            articulos: [{ paper_id: mode === 'invalid' ? 'wrong-id' : id, disponible: false }],
          },
        });
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await chooseArticle(page, 'W05-0821');
    const context = await page.getByLabel('Contexto en inglés').inputValue();
    if (mode === 'missing')
      await expect(page.getByText(/Este artículo no tiene texto preparado/)).toBeVisible();
    else await expect(page.getByText(/Esto no significa que falte el texto/)).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }),
    ).toBeDisabled();
    await expect(page.getByLabel('Contexto en inglés')).toHaveValue(context);
    await expect(selectedArticle(page)).toContainText('W05-0821');
    expect(analyses).toBe(0);
    if (mode !== 'missing') {
      retry = true;
      await page.getByRole('button', { name: 'Reintentar disponibilidad' }).click();
      await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
      await expect(
        page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }),
      ).toBeEnabled();
    }
  });
}

test('ignora una consulta antigua de disponibilidad al cambiar de artículo', async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/analisis-cita-ms/disponibilidad', async (route) => {
    const id = route.request().postDataJSON().paper_ids[0];
    if (id === 'W05-0821') await held;
    await route
      .fulfill({
        json: {
          version_contenido: 'v1',
          articulos: [{ paper_id: id, disponible: id === 'W05-0821' }],
        },
      })
      .catch(() => {});
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, 'W05-0821');
  await expect(page.getByText('Consultando texto preparado…')).toBeVisible();
  await chooseArticle(page, 'D09-1059');
  await expect(page.getByText(/Este artículo no tiene texto preparado/)).toBeVisible();
  release();
  await expect(
    page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }),
  ).toBeDisabled();
  await expect(selectedArticle(page)).toContainText('D09-1059');
});

for (const status of [404, 429, 200]) {
  test(`fallo de análisis ${status}: no muestra resultados falsos y conserva entradas`, async ({
    page,
  }) => {
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
            version_contenido: 'v1',
            articulos: [{ paper_id: 'W05-0821', disponible: true }],
          },
        });
      } else {
        await route.fulfill({
          status,
          json:
            status === 200
              ? { articulo: { paper_id: 'W05-0821', version_contenido: 'other-version' }, top3: [] }
              : {
                  detail:
                    status === 404
                      ? 'Artículo sin texto completo preparado para M/S.'
                      : 'El servicio está ocupado. Inténtalo de nuevo.',
                },
        });
      }
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await chooseArticle(page, 'W05-0821');
    const context = await page.getByLabel('Contexto en inglés').inputValue();
    await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.locator('#fragment-1')).toHaveCount(0);
    await expect(page.getByLabel('Contexto en inglés')).toHaveValue(context);
    await expect(selectedArticle(page)).toContainText('W05-0821');
    await expect(page.locator('#workflow-step-3')).toHaveAttribute('aria-current', 'step');
    await expect(page.locator('.results-loading')).toHaveCount(0);
    if (status === 404) {
      await page.getByRole('button', { name: 'Revisar artículo', exact: true }).click();
      await expect(page.locator('#article-step')).toBeVisible();
      await expect(
        page.getByText(
          'Este artículo no tiene texto preparado para recuperar los tres fragmentos.',
        ),
      ).toBeVisible();
    } else {
      await page.getByRole('button', { name: 'Volver al clasificador', exact: true }).click();
      await expect(page.getByRole('button', { name: 'Ver resultados', exact: true })).toBeEnabled();
    }
  });
}
