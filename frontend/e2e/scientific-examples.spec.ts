import { test, expect } from '@playwright/test';
import fs from 'node:fs';
const examples = JSON.parse(fs.readFileSync('src/scientificExamples.json', 'utf8'));

test('busca ejemplos, carga contexto y artículo sin ejecutar inferencia', async ({
  page,
}, info) => {
  let inferences = 0;
  await page.route('**/api/**', async (route) => {
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
  await page.getByLabel('Familia y modelo').selectOption('commercial');
  await page.getByRole('checkbox', { name: /Acepto enviar/ }).check();
  const opener = page.getByRole('button', { name: 'Explorar ejemplos del dataset' });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: 'Elige un ejemplo' });
  const search = dialog.getByRole('searchbox', { name: 'Buscar ejemplos' });
  await expect(search).toBeFocused();
  await expect(dialog.getByRole('status')).toHaveText('33 de 33 ejemplos');
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
  await expect(page.getByLabel('Artículo preparado por título e ID')).toHaveValue(chosen.paper_id);
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: /Acepto enviar/ })).not.toBeChecked();
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
