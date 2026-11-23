import { expect, type Page } from '@playwright/test';
import catalog from '../src/articleCatalog.json' with { type: 'json' };
import fullCatalog from '../src/fullArticleCatalog.json' with { type: 'json' };

export const suggestionResponse = {
  version_contenido: catalog.version_contenido,
  version_catalogo: fullCatalog.source_sha256,
  recomendaciones: catalog.articulos.slice(0, 5).map((a) => ({ ...a, similitud: 0.7 })),
};

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
