import { enterContext, chooseExample } from './context.helpers';
import { test, expect } from '@playwright/test';
import catalog from '../src/articleCatalog.json' with { type: 'json' };
import fullCatalog from '../src/fullArticleCatalog.json' with { type: 'json' };
import { selectedArticle, suggestionResponse } from './article-picker.helpers';

const context = 'Prior research TARGETCIT improves machine translation.';

test('sugerencias automáticas, confirmación manual y consulta única al volver', async ({
  page,
}, info) => {
  let calls = 0;
  let coverage = 0;
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/clasificadores')) return route.fulfill({ json: { clasificadores: [] } });
    if (path.endsWith('/disponibilidad')) {
      coverage++;
      return route.fulfill({
        json: {
          version_contenido: catalog.version_contenido,
          articulos: route
            .request()
            .postDataJSON()
            .paper_ids.map((paper_id: string) => ({ paper_id, disponible: true })),
        },
      });
    }
    if (path.endsWith('/recomendar')) {
      calls++;
      expect(route.request().postDataJSON()).toEqual({
        contexto: context,
        top_k: 5,
        modelo: 'scibert-articulos-v1',
      });
      return route.fulfill({ json: suggestionResponse });
    }
    return route.abort();
  });
  await page.goto('/');
  await page.getByLabel('Contexto en inglés').fill(context);
  expect(calls).toBe(0);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sugeridos según tu contexto' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sugerir según mi contexto' })).toHaveCount(0);
  await expect(page.locator('.article-options > li')).toHaveCount(5);
  await expect(selectedArticle(page)).toHaveCount(0);
  expect(calls).toBe(1);
  expect(coverage).toBe(0);
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeDisabled();
  await page.screenshot({ path: info.outputPath('sugerencias-automaticas.png'), fullPage: true });
  const first = page.getByRole('button', { name: /Seleccionar artículo:/ }).first();
  await first.focus();
  await page.keyboard.press('Enter');
  await expect(selectedArticle(page).getByRole('heading')).toBeFocused();
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeEnabled();
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(selectedArticle(page)).toHaveCount(1);
  expect(calls).toBe(1);
  await page.getByRole('button', { name: 'Cambiar artículo' }).click();
  const filter = page.getByRole('searchbox', { name: 'Buscar por título o ID' });
  await filter.fill('translation');
  await filter.fill('');
  await expect(page.getByText('19776 artículos', { exact: true })).toBeVisible();
  await page
    .getByRole('navigation', { name: 'Páginas de artículos' })
    .getByRole('button', { name: 'Siguiente', exact: true })
    .click();
  await expect(page.getByText('Página 2 de 3956', { exact: true })).toBeVisible();
  expect(calls).toBe(1);
});

for (const failure of ['unavailable', 'version', 'catalog', 'foreign', 'busy']) {
  test(`recuperación manual ante sugerencias automáticas ${failure}`, async ({ page }) => {
    let calls = 0;
    await page.route('**/api/clasificadores', (r) => r.fulfill({ json: { clasificadores: [] } }));
    await page.route('**/api/analisis-cita-ms/recomendar', (r) => {
      calls++;
      if (failure === 'busy')
        return r.fulfill({
          status: 429,
          json: { detail: 'Servicio ocupado. Intenta nuevamente.' },
        });
      if (failure === 'unavailable')
        return r.fulfill({ status: 503, json: { detail: 'No disponible' } });
      return r.fulfill({
        json: {
          ...suggestionResponse,
          version_contenido: failure === 'version' ? 'old' : catalog.version_contenido,
          version_catalogo: failure === 'catalog' ? 'old' : fullCatalog.source_sha256,
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
    await page.getByLabel('Contexto en inglés').fill(context);
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Puedes seguir buscando por título o ID.');
    if (['version', 'catalog', 'foreign'].includes(failure))
      await expect(page.getByRole('alert')).toContainText(
        'Las sugerencias no corresponden al catálogo actual.',
      );
    await page.getByRole('searchbox', { name: 'Buscar por título o ID' }).fill('W05-0821');
    await expect(page.getByRole('button', { name: /Seleccionar artículo:/ })).toHaveCount(1);
    await expect(selectedArticle(page)).toHaveCount(0);
    await page.getByRole('button', { name: 'Anterior', exact: true }).last().click();
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    expect(calls).toBe(1);
  });
}

test('cancelar conserva el contexto y descarta la respuesta automática tardía', async ({
  page,
}) => {
  await page.route('**/api/clasificadores', (r) => r.fulfill({ json: { clasificadores: [] } }));
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/analisis-cita-ms/recomendar', async (r) => {
    await pending;
    await r.fulfill({ json: suggestionResponse }).catch(() => {});
  });
  await page.goto('/');
  await page.getByLabel('Contexto en inglés').fill(context);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Anterior', exact: true }).last()).toBeDisabled();
  await page.getByRole('button', { name: 'Cancelar búsqueda' }).click();
  await page.getByRole('searchbox', { name: 'Buscar por título o ID' }).fill('W05-0821');
  release();
  await expect(page.locator('.article-options > li')).toHaveCount(1);
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(context);
});

test('busca todo el catálogo y bloquea artículos sin texto preparado', async ({ page }, info) => {
  const article = fullCatalog.articulos.find(
    (a) => !a.preparado && /^[A-Z][0-9]{2}-[0-9]{4}$/.test(a.paper_id),
  )!;
  let classifications = 0;
  await page.route('**/api/**', (r) => {
    if (r.request().url().endsWith('/clasificadores'))
      return r.fulfill({ json: { clasificadores: [] } });
    if (r.request().url().endsWith('/recomendar')) return r.fulfill({ json: suggestionResponse });
    if (r.request().url().endsWith('/disponibilidad'))
      return r.fulfill({
        json: {
          version_contenido: catalog.version_contenido,
          articulos: [{ paper_id: article.paper_id, disponible: false }],
        },
      });
    classifications++;
    return r.abort();
  });
  await page.goto('/');
  await page.getByLabel('Contexto en inglés').fill(context);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await page.getByRole('searchbox', { name: 'Buscar por título o ID' }).fill(article.paper_id);
  await expect(page.locator('.article-options > li')).toHaveCount(1);
  await expect(page.locator('.article-options')).toContainText('Texto pendiente');
  await page.getByRole('button', { name: /Seleccionar artículo:/ }).click();
  await expect(page.getByText(/Este artículo no tiene texto preparado/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeDisabled();
  expect(classifications).toBe(0);
  await page.screenshot({ path: info.outputPath('texto-pendiente.png'), fullPage: true });
});

test('las sugerencias admiten artículos del catálogo completo sin seleccionarlos', async ({
  page,
}, info) => {
  const article = fullCatalog.articulos.find(
    (a) => !catalog.articulos.some((p) => p.paper_id === a.paper_id),
  )!;
  await page.route('**/api/clasificadores', (r) => r.fulfill({ json: { clasificadores: [] } }));
  await page.route('**/api/analisis-cita-ms/recomendar', (r) =>
    r.fulfill({
      json: {
        ...suggestionResponse,
        recomendaciones: [
          { paper_id: article.paper_id, resumen: 'Public article abstract.', similitud: 0.7 },
        ],
      },
    }),
  );
  await page.goto('/');
  await page.getByLabel('Contexto en inglés').fill(context);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.locator('.article-options')).toContainText('Public article abstract.');
  await expect(selectedArticle(page)).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeDisabled();
  await page.screenshot({
    path: info.outputPath('sugerencias-catalogo-completo.png'),
    fullPage: true,
  });
});

test('el catálogo puede reintentarse antes de solicitar sugerencias', async ({ page }) => {
  let failed = true;
  let calls = 0;
  await page.route('**/fullArticleCatalog*.json*', (r) =>
    failed && r.request().resourceType() === 'fetch'
      ? r.fulfill({ status: 503, body: 'Unavailable' })
      : r.continue(),
  );
  await page.route('**/api/clasificadores', (r) => r.fulfill({ json: { clasificadores: [] } }));
  await page.route('**/api/analisis-cita-ms/recomendar', (r) => {
    calls++;
    return r.fulfill({ json: suggestionResponse });
  });
  await page.goto('/');
  await page.getByLabel('Contexto en inglés').fill(context);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.getByText(/No se pudo cargar el catálogo completo/)).toBeVisible();
  expect(calls).toBe(0);
  failed = false;
  await page.getByRole('button', { name: 'Reintentar catálogo' }).click();
  await expect(page.getByRole('heading', { name: 'Sugeridos según tu contexto' })).toBeVisible();
  expect(calls).toBe(1);
});

test('cargar un ejemplo no confirma artículo ni clasifica', async ({ page }) => {
  let coverage = 0;
  await page.route('**/api/**', (r) => {
    if (r.request().url().endsWith('/clasificadores'))
      return r.fulfill({ json: { clasificadores: [] } });
    if (r.request().url().endsWith('/recomendar')) return r.fulfill({ json: suggestionResponse });
    coverage++;
    return r.abort();
  });
  await page.goto('/');
  await chooseExample(page);
  await expect(selectedArticle(page)).toHaveCount(0);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sugeridos según tu contexto' })).toBeVisible();
  await expect(page.getByRole('searchbox', { name: 'Buscar por título o ID' })).toBeVisible();
  await expect(selectedArticle(page)).toHaveCount(0);
  expect(coverage).toBe(0);
});

test('avisa del recorte antes de habilitar el análisis', async ({ page }, info) => {
  await page.route('**/api/clasificadores', (r) => r.fulfill({ json: { clasificadores: [] } }));
  await page.route('**/api/analisis-cita-ms/recomendar', (r) =>
    r.fulfill({ json: suggestionResponse }),
  );
  await page.route('**/api/analisis-cita-ms/disponibilidad', (r) =>
    r.fulfill({
      json: {
        version_contenido: catalog.version_contenido,
        articulos: [
          {
            paper_id: 'W05-0821',
            disponible: true,
            truncamiento: {
              aplicado: true,
              texto_recortado: true,
              fragmentos_originales: 140,
              fragmentos_analizados: 80,
              caracteres_originales: 90000,
              caracteres_analizados: 56000,
            },
          },
        ],
      },
    }),
  );
  await page.goto('/');
  await enterContext(page);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(selectedArticle(page)).toHaveCount(0);
  await page.getByRole('searchbox', { name: 'Buscar por título o ID' }).fill('W05-0821');
  await page.getByRole('button', { name: /Seleccionar artículo:/ }).click();
  await expect(page.getByText(/Análisis limitado a los primeros 80 fragmentos/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Siguiente: clasificador' })).toBeEnabled();
  await page.screenshot({ path: info.outputPath('aviso-recorte.png'), fullPage: true });
});
