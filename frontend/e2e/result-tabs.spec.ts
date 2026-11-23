import { test, expect } from '@playwright/test';
import catalog from '../src/articleCatalog.json' with { type: 'json' };
import { meanings } from '../src/citationFunctions';
import { chooseArticle, suggestionResponse } from './article-picker.helpers';

for (const mode of ['M', 'S', 'commercial']) {
  test(`pestañas de la función predicha: ${mode}`, async ({ page }, info) => {
    let analyses = 0;
    let commercialCalls = 0;
    const labels = Object.keys(meanings);
    const classifier = {
      clase: 'Application',
      probabilidad: 0.7,
      ajuste_ph: false,
      probabilidades: labels.map((clase) => ({
        clase,
        probabilidad: clase === 'Application' ? 0.7 : 0.0375,
      })),
    };
    await page.route('**/api/**', (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/clasificadores'))
        return route.fulfill({ json: { clasificadores: [{ id: 'commercial' }] } });
      if (path.endsWith('/recomendar')) return route.fulfill({ json: suggestionResponse });
      if (path.endsWith('/disponibilidad'))
        return route.fulfill({
          json: {
            version_contenido: catalog.version_contenido,
            articulos: [{ paper_id: 'W05-0821', disponible: true }],
          },
        });
      if (path.endsWith('/articulo')) {
        analyses++;
        return route.fulfill({
          json: {
            articulo: {
              titulo: catalog.articulos.find((article) => article.paper_id === 'W05-0821')!.titulo,
              paper_id: 'W05-0821',
              version_contenido: catalog.version_contenido,
              publicacion: 'https://aclanthology.org/W05-0821/',
            },
            top3: [1, 2, 3].map((i) => ({
              chunk_id: `p${i}`,
              texto: `Fragmento verificado ${i}`,
              seccion: 'Methods',
              similitud_coseno: 0.5,
              perfil: 'method',
            })),
            clasificadores: { M: classifier, S: classifier },
            modelo_recuperacion: 'SciBERT',
            revision_scibert: 'a'.repeat(40),
            dispositivo: 'cpu',
            tokens_ab: 512,
            aviso: 'Puntuaciones del modelo, sin validación de acierto.',
          },
        });
      }
      if (path.endsWith('/comercial/clasificar')) {
        commercialCalls++;
        return route.fulfill({
          json: {
            paper_id: 'W05-0821',
            version_contenido: catalog.version_contenido,
            proveedor: 'OpenAI',
            modelo_solicitado: 'gpt-6.1-sol',
            modelo_efectivo: 'gpt-6.1-sol',
            perfil: 'zero_shot_detailed',
            sha256_prompts: 'b'.repeat(64),
            clase: 'Application',
            abstencion: null,
            puntuaciones: labels.map((clase) => ({
              clase,
              valor: clase === 'Application' ? 0.7 : 0.0375,
            })),
          },
        });
      }
      return route.abort();
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    await chooseArticle(page, 'W05-0821');
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    if (mode === 'S') await page.getByLabel('Familia y modelo').selectOption('S');
    if (mode === 'commercial') {
      await page.getByLabel('Familia y modelo').selectOption('commercial');
      await page.getByRole('checkbox', { name: /Acepto enviar/ }).check();
    }
    await page.getByRole('button', { name: 'Analizar cita', exact: true }).click();
    const result = page.locator('#analysis-results');
    const tabs = result.getByRole('tablist', { name: 'Función predicha de la cita' });
    await expect(tabs.getByRole('tab')).toHaveCount(3);
    const score = tabs.getByRole('tab', { name: 'Puntuación', exact: true });
    const details = tabs.getByRole('tab', { name: 'Detalles del análisis', exact: true });
    const help = tabs.getByRole('tab', { name: 'Ayuda', exact: true });
    await expect(score).toHaveAttribute('aria-selected', 'true');
    await expect(result.getByRole('tabpanel')).toHaveCount(1);
    const scorePanel = result.getByRole('tabpanel', { name: 'Puntuación', exact: true });
    await expect(scorePanel.locator('.function-score')).toHaveCount(9);
    await expect(result.getByText('Fragmento verificado 1', { exact: true })).toBeVisible();
    const capture = async (name: string) => {
      await expect(page.locator('body')).toHaveJSProperty(
        'scrollWidth',
        await page.locator('body').evaluate((e) => e.clientWidth),
      );
      await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: true });
    };
    await capture('puntuacion');
    await score.focus();
    await page.keyboard.press('ArrowRight');
    await expect(details).toBeFocused();
    await expect(details).toHaveAttribute('aria-selected', 'true');
    const detailsPanel = result.getByRole('tabpanel', {
      name: 'Detalles del análisis',
      exact: true,
    });
    await expect(detailsPanel.getByText(/Recuperador: SciBERT/)).toBeVisible();
    if (mode === 'commercial') {
      await expect(detailsPanel.getByText(/Modelo efectivo: gpt-6.1-sol/)).toBeVisible();
      await expect(detailsPanel.getByText(/zero_shot_detailed/)).toBeVisible();
    }
    await expect(
      result.getByRole('tabpanel', { name: 'Puntuación', exact: true, hidden: true }),
    ).toBeHidden();
    await capture('detalles');
    await page.keyboard.press('End');
    await expect(help).toBeFocused();
    const helpPanel = result.getByRole('tabpanel', { name: 'Ayuda', exact: true });
    await expect(
      helpPanel.getByRole('heading', { name: 'Qué significan las nueve funciones' }),
    ).toBeVisible();
    await expect(helpPanel.locator('dt')).toHaveCount(9);
    await expect(helpPanel.getByText(meanings.Application, { exact: true })).toBeVisible();
    await expect(result.getByText('Fragmento verificado 1', { exact: true })).toBeVisible();
    await capture('ayuda');
    await page.keyboard.press('ArrowRight');
    await expect(score).toBeFocused();
    await page.keyboard.press('ArrowLeft');
    await expect(help).toBeFocused();
    await page.keyboard.press('Home');
    await expect(score).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(scorePanel).toBeFocused();
    await help.click();
    await expect(help).toHaveAttribute('aria-selected', 'true');
    await score.click();
    await expect(scorePanel).toBeVisible();
    expect(analyses).toBe(1);
    expect(commercialCalls).toBe(mode === 'commercial' ? 1 : 0);
  });
}
