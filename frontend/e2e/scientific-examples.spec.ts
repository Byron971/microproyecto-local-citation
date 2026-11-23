import { chooseArticle, selectedArticle, suggestionResponse } from './article-picker.helpers';
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
const examples = JSON.parse(fs.readFileSync('src/scientificExamples.json', 'utf8'));

test('busca ejemplos y carga contexto sin confirmar artículo ni clasificar', async ({
  page,
}, info) => {
  let inferences = 0;
  await page.route('**/api/**', async (route) => {
    if (route.request().url().endsWith('/recomendar'))
      return route.fulfill({ json: suggestionResponse });
    if (route.request().url().endsWith('/clasificadores')) {
      await route.fulfill({ json: { clasificadores: [{ id: 'commercial' }] } });
    } else if (route.request().url().endsWith('/disponibilidad')) {
      await route.fulfill({
        json: {
          version_contenido: examples.version_contenido,
          articulos: route
            .request()
            .postDataJSON()
            .paper_ids.map((paper_id: string) => ({ paper_id, disponible: true })),
        },
      });
    } else {
      inferences++;
      await route.abort();
    }
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, 'W05-0821');
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  await page.getByLabel('Familia y modelo').selectOption('commercial');
  await page.getByRole('checkbox', { name: /Acepto enviar/ }).check();
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  const opener = page.getByRole('button', { name: 'Explorar ejemplos del dataset' });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: 'Elige un ejemplo' });
  const search = dialog.getByRole('searchbox', { name: 'Buscar ejemplos' });
  await expect(search).toBeFocused();
  await expect(dialog.getByRole('status')).toHaveText('33 de 33 ejemplos');
  await expect(dialog.locator('.example-card')).toHaveCount(10);
  await search.fill('no-existe-esta-cita');
  await expect(dialog.getByText(/No hay ejemplos/)).toBeVisible();
  const chosen = examples.ejemplos[0];
  await search.fill(chosen.context_id.toLowerCase());
  await expect(dialog.locator('.example-card')).toHaveCount(1);
  await expect(dialog.locator('.example-card')).toContainText(chosen.contexto);
  await page.screenshot({ path: info.outputPath('selector-ejemplos.png'), fullPage: true });
  await dialog.locator('.example-card').click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(chosen.contexto);
  await expect(selectedArticle(page)).toHaveCount(0);
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, chosen.paper_id);
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  await expect(page.getByLabel('Familia y modelo')).toHaveValue('M');
  await page.getByLabel('Familia y modelo').selectOption('commercial');
  await expect(page.getByRole('checkbox', { name: /Acepto enviar/ })).not.toBeChecked();
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  expect(inferences).toBe(0);
  await opener.click();
  await expect(dialog.getByText('En uso', { exact: true })).toHaveCount(1);
  await search.fill(chosen.titulo.split(/\s+/).slice(0, 2).join(' '));
  await expect(dialog.locator('.example-card').first()).toContainText(chosen.titulo);
  await search.fill(chosen.contexto.trim().split(/\s+/).slice(0, 3).join(' '));
  await expect(dialog.locator('.example-card')).not.toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(chosen.contexto);
});

test('pagina diez ejemplos y reinicia la página al buscar', async ({ page }, info) => {
  await page.route('**/api/**', (route) => route.fulfill({ json: { clasificadores: [] } }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Explorar ejemplos del dataset' }).click();
  const dialog = page.getByRole('dialog', { name: 'Elige un ejemplo' });
  const nav = dialog.getByRole('navigation', { name: 'Páginas de ejemplos' });
  await expect(dialog.locator('.example-card')).toHaveCount(10);
  await expect(nav.getByRole('button', { name: 'Anterior', exact: true })).toBeDisabled();
  for (const [index, count] of [
    [1, 10],
    [2, 10],
    [3, 3],
  ]) {
    await nav.getByRole('button', { name: 'Siguiente', exact: true }).click();
    await expect(nav).toContainText(`Página ${index + 1} de 4`);
    await expect(dialog.locator('.example-card')).toHaveCount(count);
    await expect(dialog.locator('.example-card').first()).toContainText(
      examples.ejemplos[index * 10].contexto,
    );
  }
  await expect(nav.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled();
  await page.screenshot({ path: info.outputPath('ejemplos-pagina-4.png'), fullPage: true });
  const search = dialog.getByRole('searchbox', { name: 'Buscar ejemplos' });
  await search.fill(examples.ejemplos[0].context_id);
  await expect(dialog.locator('.example-card')).toHaveCount(1);
  await expect(nav).toHaveCount(0);
  await search.fill('');
  await expect(nav).toContainText('Página 1 de 4');
  await expect(dialog.locator('.example-card')).toHaveCount(10);
  await expect(nav.getByRole('button', { name: 'Anterior', exact: true })).toBeDisabled();
  await page.screenshot({ path: info.outputPath('ejemplos-pagina-1.png'), fullPage: true });
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
});
