import { enterContext } from './context.helpers';
import { chooseArticle, selectedArticle, suggestionResponse } from './article-picker.helpers';
import { test, expect } from '@playwright/test';
import { completedJob, isAnalysisStart } from './analysis-job.helpers';

test('bloquea etapas futuras, resalta la actual y conserva los datos al volver', async ({
  page,
}, info) => {
  let inferenceCalls = 0;
  await page.route('**/api/**', async (route) => {
    if (route.request().url().endsWith('/recomendar'))
      return route.fulfill({ json: suggestionResponse });
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
  await expect(page.locator('#article-filter')).toBeDisabled();
  await expect(page.locator('#classifier-step')).toBeHidden();
  await expect(page.locator('#classifier')).toBeDisabled();
  await page.screenshot({ path: info.outputPath('paso-1.png'), fullPage: true });
  await enterContext(page);
  const context = await page.getByLabel('Contexto en inglés').inputValue();
  await expect(page.locator('#workflow-step-1')).toBeDisabled();
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await chooseArticle(page, 'W05-0821');
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
  await expect(selectedArticle(page)).toContainText('W05-0821');
  await page.getByRole('button', { name: 'Anterior', exact: true }).click();
  await expect(page.getByLabel('Contexto en inglés')).toHaveValue(context);
  await page.getByLabel('Contexto en inglés').fill('Unmarked citation context.');
  await expect(page.locator('#workflow-step-1')).toBeDisabled();
  await expect(
    page.getByRole('button', { name: 'Siguiente: artículo', exact: true }),
  ).toBeDisabled();
  expect(inferenceCalls).toBe(0);
});

for (const reset of ['context', 'dataset-example']) {
  test(`navegación libre al completar y reinicio por ${reset}`, async ({ page }, info) => {
    let inferences = 0;
    await page.route('**/api/**', async (route) => {
      if (route.request().url().endsWith('/recomendar'))
        return route.fulfill({ json: suggestionResponse });
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/clasificadores')) await route.fulfill({ json: { clasificadores: [] } });
      else if (path.endsWith('/disponibilidad'))
        await route.fulfill({
          json: {
            version_contenido: 'v1',
            articulos: route
              .request()
              .postDataJSON()
              .paper_ids.map((paper_id: string) => ({ paper_id, disponible: true })),
          },
        });
      else if (isAnalysisStart(path)) {
        inferences++;
        const classifier = {
          clase: 'Application',
          probabilidad: 0.8,
          probabilidades: Array.from({ length: 9 }, (_, i) => ({
            clase: `Clase ${i}`,
            probabilidad: i ? 0.025 : 0.8,
          })),
        };
        await route.fulfill({
          json: completedJob({
            articulo: {
              paper_id: 'W05-0821',
              titulo: 'Public article',
              version_contenido: 'v1',
              publicacion: 'https://aclanthology.org/W05-0821/',
            },
            top3: [1, 2, 3].map((i) => ({
              chunk_id: `p${i}`,
              texto: `Pasaje ${i}`,
              seccion: 'Methods',
              similitud_coseno: 0.5,
            })),
            clasificadores: { M: classifier, S: classifier },
          }),
        });
      } else throw new Error('Inferencia inesperada');
    });
    await page.goto('/');
    await enterContext(page);
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await chooseArticle(page, 'W05-0821');
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    await page.getByLabel('Familia y modelo').selectOption('S');
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Resultado del análisis' })).toBeVisible();
    for (const i of [0, 1, 2, 3]) await expect(page.locator(`#workflow-step-${i}`)).toBeEnabled();
    await expect(page.locator('.workflow-progress .step-complete')).toHaveCount(4);
    for (const i of [0, 2, 1, 3, 0]) {
      await page.locator(`#workflow-step-${i}`).click();
      await expect(page.locator(`#workflow-step-${i}`)).toHaveAttribute('aria-current', 'step');
      for (const next of [0, 1, 2, 3])
        await expect(page.locator(`#workflow-step-${next}`)).toBeEnabled();
    }
    await page.locator('#workflow-step-2').click();
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Resultado del análisis' })).toBeVisible();
    await page.locator('#workflow-step-0').click();
    expect(inferences).toBe(1);
    await page.screenshot({ path: info.outputPath('checklist-completo.png'), fullPage: true });
    if (reset === 'context')
      await page.getByLabel('Contexto en inglés').fill('New context TARGETCIT.');
    else {
      await page.getByRole('button', { name: 'Explorar ejemplos', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: 'Elige un ejemplo' });
      await dialog.getByRole('button', { name: 'Siguiente', exact: true }).click();
      const context = await dialog.locator('.example-preview').first().textContent();
      await dialog.locator('.example-card').first().click();
      await expect(page.getByLabel('Contexto en inglés')).toHaveValue(context!);
      await expect(selectedArticle(page)).toHaveCount(0);
    }
    await expect(page.locator('#workflow-step-0')).toHaveAttribute('aria-current', 'step');
    await expect(page.locator('.workflow-progress .step-complete')).toHaveCount(0);
    for (const i of [1, 2, 3]) await expect(page.locator(`#workflow-step-${i}`)).toBeDisabled();
    await expect(page.getByLabel('Familia y modelo')).toHaveValue('M');
    await expect(page.getByRole('region', { name: 'Resultado del análisis' })).toHaveCount(0);
    if (reset === 'context') await expect(selectedArticle(page)).toHaveCount(0);
    expect(inferences).toBe(1);
  });
}
