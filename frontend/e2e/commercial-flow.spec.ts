import { enterContext } from './context.helpers';
import { chooseArticle, selectedArticle, suggestionResponse } from './article-picker.helpers';
import { test, expect } from '@playwright/test';
import { completedJob, isAnalysisStart } from './analysis-job.helpers';

const labels = [
  'Background',
  'Gap',
  'Basis',
  'Comparison',
  'Application',
  'Improvement / Modification',
  'Evidence',
  'Identification of the Originator',
  'Further Reading',
];
for (const status of [200, 429, 502]) {
  test(`comercial ${status}: consentimiento y fragmentos conservados`, async ({
    page,
  }, testInfo) => {
    const calls: string[] = [];
    let finishCommercial!: () => void;
    const heldCommercial = new Promise<void>((resolve) => {
      finishCommercial = resolve;
    });
    await page.route('**/api/**', async (route) => {
      if (route.request().url().endsWith('/recomendar'))
        return route.fulfill({ json: suggestionResponse });
      const path = new URL(route.request().url()).pathname;
      if (path === '/api/clasificadores') {
        await route.fulfill({
          json: { clasificadores: [{ id: 'M' }, { id: 'S' }, { id: 'commercial' }] },
        });
      } else if (path.endsWith('/disponibilidad')) {
        await route.fulfill({
          json: {
            version_contenido: 'v1',
            articulos: [{ paper_id: 'W05-0821', disponible: true }],
          },
        });
      } else if (isAnalysisStart(path)) {
        calls.push('ms');
        const classifier = {
          clase: 'Background',
          probabilidad: 0.8,
          probabilidades: labels.map((clase) => ({ clase, probabilidad: 0.1 })),
        };
        await route.fulfill({
          json: completedJob({
            articulo: {
              paper_id: 'W05-0821',
              titulo: 'Public article',
              publicacion: 'https://aclanthology.org/W05-0821/',
              version_contenido: 'v1',
            },
            top3: [1, 2, 3].map((i) => ({
              chunk_id: `p${i}`,
              texto: `Fragmento recuperado ${i}`,
              seccion: 'Methods',
              similitud_coseno: 0.5,
            })),
            clasificadores: { M: classifier, S: classifier },
          }),
        });
      } else if (path === '/api/comercial/clasificar') {
        calls.push('commercial');
        if (status === 200) await heldCommercial;
        expect(route.request().postDataJSON()).toMatchObject({
          paper_id: 'W05-0821',
          consentimiento: true,
        });
        await route.fulfill({
          status,
          json:
            status !== 200
              ? { detail: 'Comercial no disponible para esta solicitud.' }
              : {
                  paper_id: 'W05-0821',
                  version_contenido: 'v1',
                  proveedor: 'OpenAI',
                  modelo_solicitado: 'gpt-6.1-sol',
                  modelo_efectivo: 'gpt-6.1-sol',
                  perfil: 'zero_shot_detailed',
                  sha256_prompts: 'test',
                  clase: 'Application',
                  abstencion: null,
                  puntuaciones: labels.map((clase) => ({
                    clase,
                    valor: clase === 'Application' ? 0.8 : 0.1,
                  })),
                },
        });
      } else await route.abort();
    });
    await page.goto('/');
    await enterContext(page);
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await chooseArticle(page, 'W05-0821');
    await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    await expect(page.locator('#classifier option[value="commercial"]')).toHaveCount(1);
    await page.getByLabel('Familia y modelo').selectOption('commercial');
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Confirma el envío');
    expect(calls).toEqual([]);
    await page.getByRole('checkbox', { name: /Acepto enviar/ }).check();
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    await expect(page.getByText('Fragmento recuperado 1', { exact: true })).toBeVisible();
    const panel = page.getByRole('region', { name: 'Clasificación comercial' });
    if (status === 200) {
      await expect(
        panel.getByText('Top-3 listo. Esperando la clasificación de OpenAI…'),
      ).toBeVisible();
      await expect(page.getByRole('button', { name: 'Volver al clasificador' })).toBeDisabled();
      await expect(page.locator('#workflow-step-3')).toHaveAttribute('aria-current', 'step');
      await expect(
        page.getByRole('status').filter({ hasText: 'Clasificando la función de la cita' }),
      ).toBeVisible();
      await page.screenshot({
        path: testInfo.outputPath('commercial-loading.png'),
        fullPage: true,
      });
      finishCommercial();
      await expect(panel.getByText('Application', { exact: true }).first()).toBeVisible();
      await expect(panel.getByText('0.800')).toBeVisible();
      await expect(
        panel.getByText('Utiliza un método, técnica o herramienta sin modificarlo.'),
      ).toBeVisible();
      await expect(panel.locator('.function-score-track')).toHaveCount(9);
      await expect(page.getByRole('region', { name: 'Resultado del análisis' })).toBeFocused();
      await expect(panel.getByText(/no son probabilidades calibradas/)).toBeVisible();
    } else {
      await expect(page.getByRole('alert')).toContainText('Comercial no disponible');
      await expect(panel.getByText(/Sin clasificación comercial/)).toBeVisible();
    }
    await expect(page.locator('body')).toHaveJSProperty(
      'scrollWidth',
      await page.locator('body').evaluate((e) => e.clientWidth),
    );
    if (status === 200)
      await page.screenshot({ path: testInfo.outputPath('commercial-ready.png'), fullPage: true });
    expect(calls).toEqual(['ms', 'commercial']);
    await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Modelo S', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Editar contexto', exact: true }).click();
    if (status === 200) await expect(page.locator('#workflow-step-3')).toBeEnabled();
    else {
      for (const i of [1, 2, 3]) await expect(page.locator(`#workflow-step-${i}`)).toBeDisabled();
    }
    await page.getByLabel('Contexto en inglés').fill('Contexto editado TARGETCIT.');
    for (const i of [1, 2, 3]) await expect(page.locator(`#workflow-step-${i}`)).toBeDisabled();
    await expect(page.getByText('Fragmento recuperado 1', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await expect(selectedArticle(page)).toHaveCount(0);
    await chooseArticle(page, 'W05-0821');
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    await expect(page.getByLabel('Familia y modelo')).toHaveValue('M');
    await page.getByLabel('Familia y modelo').selectOption('commercial');
    await expect(page.getByRole('checkbox', { name: /Acepto enviar/ })).not.toBeChecked();
  });
}
