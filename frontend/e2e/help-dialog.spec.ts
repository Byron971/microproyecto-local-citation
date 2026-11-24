import { chooseArticle, suggestionResponse } from './article-picker.helpers';
import { test, expect } from '@playwright/test';

test('ayuda modal accesible, conserva contexto y vuelve al control de apertura', async ({
  page,
}, info) => {
  let inferences = 0;
  await page.route('**/api/**', (route) => {
    if (route.request().url().endsWith('/clasificadores'))
      return route.fulfill({ json: { clasificadores: [{ id: 'commercial' }] } });
    if (route.request().url().endsWith('/recomendar'))
      return route.fulfill({ json: suggestionResponse });
    if (route.request().url().endsWith('/disponibilidad'))
      return route.fulfill({
        json: { version_contenido: 'v1', articulos: [{ paper_id: 'W05-0821', disponible: true }] },
      });
    inferences++;
    return route.abort();
  });
  await page.goto('/');
  const context = page.getByLabel('Contexto en inglés');
  await context.fill('Earlier research [1] introduced this method.');
  const opener = page.getByRole('button', { name: 'Ayuda', exact: true });
  await expect(page.locator('#ayuda')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Usar ejemplo público' })).toHaveCount(0);
  const explore = page.getByRole('button', { name: 'Explorar ejemplos', exact: true });
  const next = page.getByRole('button', { name: 'Siguiente: artículo', exact: true });
  const [exploreBox, nextBox] = await Promise.all([explore.boundingBox(), next.boundingBox()]);
  expect(Math.abs(exploreBox!.y - nextBox!.y)).toBeLessThan(2);
  await page.screenshot({ path: info.outputPath('contexto-acciones.png'), fullPage: true });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: 'Cómo analizar una cita', exact: true });
  await expect(dialog).toBeVisible();
  expect(await dialog.evaluate((e) => e.matches(':modal'))).toBe(true);
  await expect(dialog.getByRole('heading', { name: 'Cómo analizar una cita' })).toBeFocused();
  await expect(dialog.locator('.help-workflow li')).toHaveCount(4);
  await expect(dialog.getByText('TARGETCIT', { exact: true })).toBeVisible();
  const close = dialog.getByRole('button', { name: 'Cerrar ayuda' });
  await page.keyboard.press('Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  expect(await dialog.evaluate((e) => e.contains(document.activeElement))).toBe(true);
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
  await page.screenshot({ path: info.outputPath('ayuda-modal.png'), fullPage: true });
  await dialog.locator('.help-dialog-content').evaluate((e) => {
    e.scrollTop = e.scrollHeight;
  });
  await expect(dialog.locator('.help-interpretation')).toBeInViewport();
  await expect(close).toBeInViewport();
  await page.screenshot({ path: info.outputPath('ayuda-interpretacion.png'), fullPage: true });
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await expect(context).toHaveValue('Earlier research [1] introduced this method.');
  await opener.click();
  await close.click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await next.click();
  await chooseArticle(page, 'W05-0821');
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  await page.getByLabel('Familia y modelo').selectOption('commercial');
  const consent = page.getByRole('checkbox', { name: /Acepto enviar/ });
  await consent.check();
  await opener.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();
  await expect(page.getByLabel('Familia y modelo')).toHaveValue('commercial');
  await expect(consent).toBeChecked();
  await expect(page.locator('#workflow-step-2')).toHaveAttribute('aria-current', 'step');
  expect(inferences).toBe(0);
});
