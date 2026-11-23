import { test, expect } from '@playwright/test';
import catalog from '../src/articleCatalog.json' with { type: 'json' };
import { selectedArticle } from './article-picker.helpers';

test('sugerencias explícitas, confirmación por teclado y búsqueda paginada', async ({
  page,
}, info) => {
  let calls = 0;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/clasificadores')) return route.fulfill({ json: { clasificadores: [] } });
    if (path.endsWith('/disponibilidad'))
      return route.fulfill({
        json: {
          version_contenido: catalog.version_contenido,
          articulos: route
            .request()
            .postDataJSON()
            .paper_ids.map((paper_id: string) => ({ paper_id, disponible: true })),
        },
      });
    if (path.endsWith('/recomendar')) {
      calls++;
      expect(route.request().postDataJSON()).toMatchObject({
        top_k: 5,
        modelo: 'scibert-articulos-v1',
      });
      return route.fulfill({
        json: {
          version_contenido: catalog.version_contenido,
          recomendaciones: catalog.articulos
            .slice(0, 5)
            .map((a) => ({ paper_id: a.paper_id, similitud: 0.7 })),
        },
      });
    }
    return route.abort();
  });
  await page.goto('/');
  await page
    .getByLabel('Contexto en inglés')
    .fill('Prior research TARGETCIT improves machine translation.');
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  expect(calls).toBe(0);
  await expect(page.locator('.article-options > li')).toHaveCount(5);
  await page
    .getByRole('navigation', { name: 'Páginas de artículos' })
    .getByRole('button', { name: 'Siguiente', exact: true })
    .click();
  await expect(page.getByText('Página 2 de 8', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sugerir según mi contexto' }).click();
  await expect(page.getByRole('heading', { name: 'Sugeridos según tu contexto' })).toBeVisible();
  expect(calls).toBe(1);
  await expect(selectedArticle(page)).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeDisabled();
  await expect(
    page.getByText(
      'Son candidatos relacionados, no una identificación de la referencia. Confirma el título y la fuente.',
    ),
  ).toBeVisible();
  await page.screenshot({ path: info.outputPath('sugerencias.png'), fullPage: true });
  const card = page.getByRole('button', { name: /Seleccionar artículo:/ }).first();
  await card.focus();
  await page.keyboard.press('Enter');
  await expect(selectedArticle(page)).toContainText(catalog.articulos[0].paper_id);
  await expect(selectedArticle(page).getByRole('heading')).toBeFocused();
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeEnabled();
});

for (const failure of ['unavailable', 'version', 'foreign', 'busy']) {
  test(`recuperación manual ante sugerencias ${failure}`, async ({ page }) => {
    await page.route('**/api/clasificadores', (route) =>
      route.fulfill({ json: { clasificadores: [] } }),
    );
    await page.route('**/api/analisis-cita-ms/recomendar', (route) => {
      if (failure === 'busy')
        return route.fulfill({
          status: 429,
          json: { detail: 'Servicio ocupado. Intenta nuevamente.' },
        });
      if (failure === 'unavailable')
        return route.fulfill({ status: 503, json: { detail: 'No disponible' } });
      return route.fulfill({
        json: {
          version_contenido: failure === 'version' ? 'old' : catalog.version_contenido,
          recomendaciones: [
            {
              paper_id: failure === 'foreign' ? 'UNKNOWN' : catalog.articulos[0].paper_id,
              similitud: 0.5,
            },
          ],
        },
      });
    });
    await page.goto('/');
    await page
      .getByLabel('Contexto en inglés')
      .fill('Prior research TARGETCIT improves machine translation.');
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await page.getByRole('button', { name: 'Sugerir según mi contexto' }).click();
    await expect(page.getByRole('alert')).toContainText('Puedes seguir buscando por título o ID.');
    await page.getByRole('searchbox', { name: 'Buscar por título o ID' }).fill('W05-0821');
    await expect(page.getByRole('button', { name: /Seleccionar artículo:/ })).toHaveCount(1);
    await expect(selectedArticle(page)).toHaveCount(0);
  });
}

test('cancelar la búsqueda conserva el contexto y permite continuar manualmente', async ({
  page,
}) => {
  await page.route('**/api/clasificadores', (r) => r.fulfill({ json: { clasificadores: [] } }));
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/analisis-cita-ms/recomendar', async (route) => {
    await pending;
    await route
      .fulfill({ json: { version_contenido: catalog.version_contenido, recomendaciones: [] } })
      .catch(() => {});
  });
  await page.goto('/');
  await page
    .getByLabel('Contexto en inglés')
    .fill('Prior research TARGETCIT improves machine translation.');
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await page.getByRole('button', { name: 'Sugerir según mi contexto' }).click();
  await expect(page.getByRole('button', { name: 'Anterior', exact: true }).last()).toBeDisabled();
  await page.getByRole('button', { name: 'Cancelar búsqueda' }).click();
  release();
  await page.getByRole('searchbox', { name: 'Buscar por título o ID' }).fill('W05-0821');
  await expect(page.locator('.article-options > li')).toHaveCount(1);
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(
    'Prior research TARGETCIT improves machine translation.',
  );
});
