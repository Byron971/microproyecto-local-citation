import { expect, type Page } from '@playwright/test';

export const selectedArticle = (page: Page) =>
  page.locator('#article-step [aria-label="Artículo seleccionado"]');
export async function chooseArticle(page: Page, id: string) {
  const filter = page.getByRole('searchbox', { name: 'Buscar por título o ID', exact: true });
  if (!(await filter.isVisible()))
    await page.getByRole('button', { name: 'Cambiar artículo', exact: true }).click();
  await filter.fill(id);
  await page.getByRole('button', { name: new RegExp(`Seleccionar artículo: .*${id}`) }).click();
  await expect(selectedArticle(page)).toContainText(id);
}
