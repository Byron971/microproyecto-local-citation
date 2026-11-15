import { test, expect } from '@playwright/test';
import fs from 'node:fs';
const referenceBibtex = fs.readFileSync('src/test/fixtures/acl-P14-1062.bib', 'utf8');
const insights = JSON.parse(fs.readFileSync('../data/processed/dashboard_insights.json', 'utf8'));
// Transporte de prueba; las aserciones cubren la app real y no fabrican modelos nuevos.
const model = {
  id: 'tfidf_reranker_v1',
  nombre: 'TF-IDF + reordenador lineal',
  descripcion: 'Recupera 100 candidatos del corpus ACL-200 y los reordena con regresión logística.',
  disponible: true,
  motivo: null,
  puntaje: {
    etiqueta: 'Puntaje del reordenador',
    descripcion: 'Puntaje estimado para ordenar candidatos; no garantiza que la cita sea correcta.',
  },
  devuelve_tfidf: true,
};
test.beforeEach(async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const data: Record<string, unknown> = {
      '/api/referencias/P14-1062': {
        paper_id: 'P14-1062',
        bibtex: referenceBibtex,
        source_url: 'https://aclanthology.org/P14-1062/',
      },
      '/api/estado': { listo: true, modelo: {} },
      '/api/modelos': { predeterminado: model.id, modelos: [model] },
      '/api/insights': insights,
      '/api/ejemplos': {
        total: 2,
        particion: 'val',
        ejemplos: [
          {
            context_id: 'real-1',
            texto: 'Neural networks learn distributed representations of natural language.',
            cita_correcta: 'P14-1062',
            titulo_correcto: 'A Convolutional Neural Network for Modelling Sentences',
          },
          {
            context_id: 'real-2',
            texto: 'Translation systems compare language models.',
            cita_correcta: 'P13-1045',
            titulo_correcto:
              'Learning Distributed Representations for Structured Natural Language Prediction',
          },
        ],
      },
      '/api/recomendar': {
        modelo: model.id,
        total: 2,
        recomendaciones: [
          {
            posicion: 1,
            paper_id: 'P14-1062',
            titulo: 'A Convolutional Neural Network for Modelling Sentences',
            resumen:
              'We propose an unsupervised algorithm that learns fixed-length feature representations from variable-length pieces of texts, such as sentences, paragraphs, and documents.',
            similitud: 0.9123,
            similitud_tfidf: 0.3412,
          },
          {
            posicion: 2,
            paper_id: 'P13-1045',
            titulo:
              'Learning Distributed Representations for Structured Natural Language Prediction',
            resumen:
              'Distributed representations of language offer a way to learn useful features for prediction tasks.',
            similitud: 0.8214,
            similitud_tfidf: 0.282,
          },
        ],
      },
    };
    await route.fulfill({
      status: data[path] ? 200 : 404,
      contentType: 'application/json',
      body: JSON.stringify(data[path] || { detail: 'Not found' }),
    });
  });
});
test('ejemplo, resultados accesibles, navegación directa y ancho móvil', async ({
  page,
  context,
}, testInfo) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Encuentra referencias' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Referencias recomendadas/ })).toHaveCount(0);
  await expect(page.getByLabel('Modelo', { exact: true })).toBeVisible();
  await expect(
    page.getByText('Busca artículos relacionados con un fragmento de tu texto.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Qué hace este modelo' }).click();
  await expect(page.getByRole('note')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.screenshot({ path: testInfo.outputPath('initial.png'), fullPage: true });
  await page.getByLabel('Resultados', { exact: true }).selectOption('5');
  await page.getByRole('button', { name: 'Usar un ejemplo' }).click();
  await expect(page.getByRole('dialog', { name: 'Elige un ejemplo' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('examples.png'), fullPage: true });
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Usar un ejemplo' })).toBeFocused();
  await page.getByRole('button', { name: 'Usar un ejemplo' }).click();
  await page
    .getByRole('button', { name: /A Convolutional Neural Network for Modelling Sentences/ })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: 'Recomendar' }).click();
  await expect(page.getByText(/cita correcta/i)).toHaveCount(0);
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.getByRole('button', { name: 'Copiar referencia APA 7 de P14-1062' }).click();
  await expect(page.getByText('Referencia APA 7 copiada.', { exact: true })).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain('Kalchbrenner, N., Grefenstette, E., & Blunsom, P. (2014).');
  expect(copied).toContain('https://doi.org/10.3115/v1/P14-1062');

  await expect(
    page.getByRole('button', { name: 'A Convolutional Neural Network for Modelling Sentences' }),
  ).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath('recommendations.png'), fullPage: true });
  await page.getByText('Explorar', { exact: true }).click();
  await page.getByRole('link', { name: 'Datos', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'El corpus, de cerca.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Calidad e integridad' })).toBeVisible();
  await page.goto('/modelo');
  await expect(page.getByRole('heading', { name: 'Qué recupera la línea base.' })).toBeVisible();
  await page.goto('/negativos');
  await expect(
    page.getByRole('heading', { name: 'Aprender de los casos difíciles.' }),
  ).toBeVisible();
  await page.goto('/fragmentos');
  await expect(
    page.getByRole('heading', { name: 'Clasificación aún no disponible' }),
  ).toBeVisible();
});
