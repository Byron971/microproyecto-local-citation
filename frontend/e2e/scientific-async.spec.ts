import { test, expect } from '@playwright/test';
import catalog from '../src/articleCatalog.json' with { type: 'json' };
import { chooseArticle, suggestionResponse } from './article-picker.helpers';

for (const failure of [false, true]) {
  test(`espera una sola ejecución; expiración=${failure}`, async ({ page }) => {
    let starts = 0;
    let polls = 0;
    const id = 'a'.repeat(32);
    const pending = { estado: 'procesando', trabajo_id: id };
    const classifier = {
      clase: 'Application',
      probabilidad: 0.6,
      probabilidades: Array.from({ length: 9 }, (_, i) => ({
        clase: `Clase ${i}`,
        probabilidad: i ? 0.05 : 0.6,
      })),
    };
    await page.route('**/api/**', (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/clasificadores')) return route.fulfill({ json: { clasificadores: [] } });
      if (path.endsWith('/recomendar')) return route.fulfill({ json: suggestionResponse });
      if (path.endsWith('/disponibilidad'))
        return route.fulfill({
          json: {
            version_contenido: catalog.version_contenido,
            articulos: [{ paper_id: 'W05-0821', disponible: true }],
          },
        });
      if (path.endsWith('/articulo')) {
        starts++;
        expect(route.request().postDataJSON().asincrono).toBe(true);
        return route.fulfill({ status: 202, json: pending });
      }
      expect(path).toBe(`/api/analisis-cita-ms/articulo/${id}`);
      expect(route.request().method()).toBe('GET');
      polls++;
      if (polls === 1) return route.fulfill({ status: 202, json: pending });
      if (failure)
        return route.fulfill({
          status: 410,
          json: { detail: 'El análisis expiró. Tu contexto se conserva.' },
        });
      return route.fulfill({
        json: {
          articulo: {
            paper_id: 'W05-0821',
            titulo: 'Article',
            version_contenido: catalog.version_contenido,
          },
          top3: [1, 2, 3].map((i) => ({
            chunk_id: `p${i}`,
            texto: `Fragmento ${i}`,
            seccion: 'Methods',
            similitud_coseno: 0.5,
          })),
          clasificadores: { M: classifier, S: classifier },
          tokens_ab: 512,
          dispositivo: 'cpu',
        },
      });
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await chooseArticle(page, 'W05-0821');
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    if (failure) {
      await expect(page.getByRole('alert')).toContainText('El análisis expiró.');
      await expect(page.locator('#workflow-step-3')).toHaveAttribute('aria-current', 'step');
      await page.getByRole('button', { name: 'Volver al clasificador', exact: true }).click();
      await page.getByRole('button', { name: 'Anterior', exact: true }).click();
      await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
      await expect(
        page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }),
      ).toBeEnabled();
    } else {
      await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toBeVisible();
      await expect(
        page.locator('#fragment-3').getByText('Fragmento 3', { exact: true }),
      ).toBeVisible();
    }
    expect(starts).toBe(1);
    expect(polls).toBe(2);
  });
}
