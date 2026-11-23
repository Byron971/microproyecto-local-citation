import { test, expect } from '@playwright/test';
import catalog from '../src/articleCatalog.json' with { type: 'json' };
import { meanings } from '../src/citationFunctions';
import { chooseArticle, suggestionResponse } from './article-picker.helpers';

for (const mode of ['M', 'S', 'commercial']) {
  test(`pestañas de la función predicha: ${mode}`, async ({ page }, info) => {
    let analyses = 0;
    let commercialCalls = 0;
    const labels = Object.keys(meanings);
    const truncation =
      mode === 'S'
        ? {
            aplicado: true,
            texto_recortado: true,
            fragmentos_originales: 92,
            fragmentos_analizados: 75,
            caracteres_originales: 70000,
            caracteres_analizados: 55994,
          }
        : undefined;
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
            articulos: [{ paper_id: 'W05-0821', disponible: true, truncamiento: truncation }],
          },
        });
      if (path.endsWith('/articulo')) {
        analyses++;
        return route.fulfill({
          json: {
            articulo: {
              truncamiento: truncation,
              titulo: catalog.articulos.find((article) => article.paper_id === 'W05-0821')!.titulo,
              paper_id: 'W05-0821',
              version_contenido: catalog.version_contenido,
              publicacion: 'https://aclanthology.org/W05-0821/',
            },
            top3: [1, 2, 3].map((i) => ({
              chunk_id: ['p00000-p00001', 'p00006-p00007', 'p00028-p00029'][i - 1],
              texto: `Fragmento verificado ${i}`,
              seccion: 'Methods',
              similitud_coseno: 0.5,
              perfil: 'method',
            })),
            clasificadores: { M: classifier, S: classifier },
            modelo_recuperacion: 'scibert_base_mean_pooling_cosine',
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
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    const result = page.locator('#analysis-results');
    const tabs = result.getByRole('tablist', { name: 'Función predicha de la cita' });
    await expect(tabs.getByRole('tab')).toHaveCount(3);
    const score = tabs.getByRole('tab', { name: 'Puntuación', exact: true });
    const details = tabs.getByRole('tab', { name: 'Detalles del análisis', exact: true });
    const help = tabs.getByRole('tab', { name: 'Funciones de cita', exact: true });
    await expect(score).toHaveAttribute('aria-selected', 'true');
    await expect(result.getByRole('tabpanel')).toHaveCount(1);
    const scorePanel = result.getByRole('tabpanel', { name: 'Puntuación', exact: true });
    await expect(scorePanel.locator('.function-score')).toHaveCount(9);
    if (mode !== 'commercial')
      await expect(
        scorePanel.getByRole('heading', { name: `Modelo ${mode}`, exact: true }),
      ).toBeVisible();
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
    await expect(
      detailsPanel
        .getByRole('region', { name: 'Resumen del análisis' })
        .getByText('SciBERT', { exact: true }),
    ).toBeVisible();
    await expect(detailsPanel.getByRole('table')).toBeVisible();
    await expect(detailsPanel.getByRole('rowheader')).toHaveCount(3);
    await expect(detailsPanel.getByText('a'.repeat(40), { exact: true })).toBeHidden();
    await expect(detailsPanel.getByText('CPU', { exact: true })).toBeHidden();
    if (mode === 'commercial') {
      await expect(detailsPanel.getByText('gpt-6.1-sol', { exact: true })).toBeVisible();
      await expect(detailsPanel.getByText('zero_shot_detailed', { exact: true })).toBeHidden();
    }
    await expect(
      result.getByRole('tabpanel', { name: 'Puntuación', exact: true, includeHidden: true }),
    ).toBeHidden();
    if (mode === 'S')
      await expect(detailsPanel.getByText('75 de 92 fragmentos', { exact: true })).toBeVisible();
    await capture('detalles');
    await detailsPanel.screenshot({ path: info.outputPath('panel-detalles.png') });
    await detailsPanel.getByRole('link', { name: 'Fragmento 2', exact: true }).click();
    await expect(page.locator('#fragment-2')).toBeFocused();
    await expect(details).toHaveAttribute('aria-selected', 'true');
    const technical = detailsPanel.locator('summary');
    await technical.focus();
    await page.keyboard.press('Enter');
    await expect(detailsPanel.getByText('a'.repeat(40), { exact: true })).toBeVisible();
    await expect(detailsPanel.getByText('CPU', { exact: true })).toBeVisible();
    if (mode === 'commercial')
      await expect(detailsPanel.getByText('zero_shot_detailed', { exact: true })).toBeVisible();
    await capture('detalles-tecnicos');
    await page.keyboard.press('Enter');
    await details.focus();
    await page.keyboard.press('End');
    await expect(help).toBeFocused();
    const helpPanel = result.getByRole('tabpanel', { name: 'Funciones de cita', exact: true });
    await expect(
      helpPanel.getByRole('heading', { name: 'Qué significan las nueve funciones' }),
    ).toBeVisible();
    await expect(helpPanel.locator('dt')).toHaveCount(9);
    for (const [label, definition] of Object.entries(meanings)) {
      await expect(helpPanel.locator('dt').getByText(label, { exact: true })).toHaveAttribute(
        'lang',
        'en',
      );
      await expect(helpPanel.locator('dd').getByText(definition, { exact: true })).toBeVisible();
    }
    await expect(helpPanel.getByText('Aplicación', { exact: true })).toBeVisible();
    await expect(helpPanel.getByText('Fuente original', { exact: true })).toBeVisible();
    const guideSurface = helpPanel.locator('.result-info-surface');
    const detailsSurface = result
      .getByRole('tabpanel', { name: 'Detalles del análisis', exact: true, includeHidden: true })
      .locator('.result-info-surface');
    for (const property of ['backgroundColor', 'borderRadius', 'padding']) {
      expect(
        await guideSurface.evaluate(
          (element, name) => getComputedStyle(element)[name as keyof CSSStyleDeclaration],
          property,
        ),
      ).toBe(
        await detailsSurface.evaluate(
          (element, name) => getComputedStyle(element)[name as keyof CSSStyleDeclaration],
          property,
        ),
      );
    }
    await expect(helpPanel.getByText(meanings.Application, { exact: true })).toBeVisible();
    await expect(result.getByText('Fragmento verificado 1', { exact: true })).toBeVisible();
    await capture('funciones-de-cita');
    await helpPanel.screenshot({ path: info.outputPath('panel-funciones.png') });
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
