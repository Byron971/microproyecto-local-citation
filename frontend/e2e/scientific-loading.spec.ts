import { enterContext } from './context.helpers';
import { test, expect } from '@playwright/test';
import { chooseArticle, suggestionResponse } from './article-picker.helpers';
import { completedJob, isAnalysisStart } from './analysis-job.helpers';

for (const variant of ['M', 'S']) {
  test(`resultados muestran espera inmediata y conservan numeración: ${variant}`, async ({
    page,
  }, info) => {
    let calls = 0;
    let finish!: () => void;
    const pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const classifier = {
      clase: 'Application',
      probabilidad: 0.8,
      probabilidades: Array.from({ length: 9 }, (_, i) => ({
        clase: `Clase ${i}`,
        probabilidad: i ? 0.025 : 0.8,
      })),
    };
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/clasificadores')) return route.fulfill({ json: { clasificadores: [] } });
      if (path.endsWith('/recomendar')) return route.fulfill({ json: suggestionResponse });
      if (path.endsWith('/disponibilidad'))
        return route.fulfill({
          json: {
            version_contenido: 'v1',
            articulos: [{ paper_id: 'W05-0821', disponible: true }],
          },
        });
      if (isAnalysisStart(path)) {
        calls++;
        await pending;
        return route.fulfill({
          json: completedJob({
            articulo: { paper_id: 'W05-0821', titulo: 'Public article', version_contenido: 'v1' },
            top3: [1, 2, 3].map((i) => ({
              chunk_id: `p${i}`,
              texto: `Pasaje ${i}`,
              seccion: 'Methods',
              similitud_coseno: 0.5,
            })),
            clasificadores: { M: classifier, S: classifier },
          }),
        });
      }
      return route.abort();
    });
    const numbers = async () => {
      for (let i = 0; i < 4; i++)
        await expect(page.locator(`#workflow-step-${i} b`)).toHaveText(String(i + 1));
    };
    await page.goto('/');
    await numbers();
    await enterContext(page);
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await chooseArticle(page, 'W05-0821');
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    await page.getByLabel('Familia y modelo').selectOption(variant);
    if (variant === 'S') await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    await expect(page.locator('#workflow-step-3')).toHaveAttribute('aria-current', 'step');
    await expect(page.locator('#classifier-step')).toBeHidden();
    await expect(page.locator('#workflow-title-3')).toBeFocused();
    await expect(
      // Antes de que el servidor confirme la admisión no se afirma cola ni cálculo.
      page.getByRole('status').filter({ hasText: 'Enviando el análisis' }),
    ).toBeVisible();
    await expect(page.locator('.workflow-progress .step-complete')).toHaveCount(3);
    await expect(page.getByText('Análisis completado', { exact: true })).toHaveCount(0);
    for (let i = 0; i < 4; i++) await expect(page.locator(`#workflow-step-${i}`)).toBeDisabled();
    await numbers();
    if (variant === 'S')
      await expect(page.locator('.analysis-spinner')).toHaveCSS('animation-name', 'none');
    await expect(page.locator('body')).toHaveJSProperty(
      'scrollWidth',
      await page.locator('body').evaluate((e) => e.clientWidth),
    );
    await page.screenshot({ path: info.outputPath('resultados-cargando.png'), fullPage: true });
    finish();
    await expect(
      page.getByRole('heading', { name: `Modelo ${variant}`, exact: true }),
    ).toBeVisible();
    await expect(page.locator('#analysis-results')).toBeFocused();
    await expect(page.locator('.results-loading')).toHaveCount(0);
    await expect(page.locator('.workflow-progress .step-complete')).toHaveCount(4);
    await numbers();
    await page.screenshot({ path: info.outputPath('resultados-completos.png'), fullPage: true });
    await page.getByRole('button', { name: 'Volver al clasificador', exact: true }).click();
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: `Modelo ${variant}`, exact: true }),
    ).toBeVisible();
    await expect(page.locator('.results-loading')).toHaveCount(0);
    expect(calls).toBe(1);
  });
}
