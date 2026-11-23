import { test, expect } from '@playwright/test';

test('bloquea etapas futuras, resalta la actual y conserva los datos al volver', async ({
  page,
}, info) => {
  let inferenceCalls = 0;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/clasificadores')) await route.fulfill({ json: { clasificadores: [] } });
    else if (path.endsWith('/disponibilidad'))
      await route.fulfill({
        json: { version_contenido: 'v1', articulos: [{ paper_id: 'W05-0821', disponible: true }] },
      });
    else {
      inferenceCalls++;
      await route.abort();
    }
  });
  await page.goto('/');
  await expect(page.locator('#workflow-step-0')).toHaveAttribute('aria-current', 'step');
  for (const i of [1, 2, 3]) await expect(page.locator(`#workflow-step-${i}`)).toBeDisabled();
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeDisabled();
  await expect(page.locator('#article-step')).toBeHidden();
  await expect(page.locator('#cited-article')).toBeDisabled();
  await expect(page.locator('#classifier-step')).toBeHidden();
  await expect(page.locator('#classifier')).toBeDisabled();
  await page.screenshot({ path: info.outputPath('paso-1.png'), fullPage: true });
  await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
  const context = await page.getByLabel('Contexto en inglés').inputValue();
  await expect(page.locator('#workflow-step-1')).toBeDisabled();
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.locator('#workflow-step-1')).toHaveAttribute('aria-current', 'step');
  await expect(page.locator('#citation-step')).toBeHidden();
  await expect(page.getByLabel('Contexto en inglés')).toBeDisabled();
  await expect(page.locator('#article-step')).toBeVisible();
  await expect(page.locator('#workflow-step-2')).toBeDisabled();
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  await expect(page.locator('#workflow-step-2')).toHaveAttribute('aria-current', 'step');
  await expect(page.locator('#article-step')).toBeHidden();
  await expect(page.locator('#classifier-step')).toBeVisible();
  await expect(page.locator('#workflow-step-3')).toBeDisabled();
  await page.screenshot({ path: info.outputPath('paso-3.png'), fullPage: true });
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  await expect(page.getByLabel('Artículo preparado por título e ID')).toHaveValue('W05-0821');
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(context);
  await page.getByLabel('Contexto en inglés').fill('Unmarked citation context.');
  await expect(page.locator('#workflow-step-1')).toBeDisabled();
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeDisabled();
  expect(inferenceCalls).toBe(0);
});
