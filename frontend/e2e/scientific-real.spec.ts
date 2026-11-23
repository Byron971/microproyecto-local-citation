import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test.skip(!process.env.LIVE_SCIENCE_E2E, 'Requiere un servicio M/S disponible.');
test('ejemplo público completa el flujo con M/S real y textos del artículo', async ({
  page,
}, testInfo) => {
  test.setTimeout(90000);
  const corpus = JSON.parse(fs.readFileSync('../config/corpus_ms.json', 'utf8'));
  await page.goto('/');
  await expect(page.locator('#classifier option[value="open"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
  await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
  await expect(page.getByLabel('Artículo preparado por título e ID')).toHaveValue('W05-0821');
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/api/analisis-cita-ms/articulo'),
    { timeout: 60000 },
  );
  await page.getByRole('button', { name: 'Analizar cita', exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const data = await response.json();
  expect(data.articulo.paper_id).toBe('W05-0821');
  expect(data.top3).toHaveLength(3);
  expect(new Set(data.top3.map((chunk: { chunk_id: string }) => chunk.chunk_id)).size).toBe(3);
  const chunks = corpus.documentos['W05-0821'].candidatos;
  for (const fragment of data.top3) {
    expect(
      chunks.find((chunk: { chunk_id: string }) => chunk.chunk_id === fragment.chunk_id)?.texto,
    ).toBe(fragment.texto);
    await expect(page.getByText(fragment.texto, { exact: true })).toBeVisible();
  }
  await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: /Ver fuente del fragmento/ })).toHaveCount(3);
  await expect(
    page
      .getByText(
        /Utiliza un método|Presenta información|Compara métodos|Señala una limitación|Usa el trabajo|Adapta, amplía|Aporta respaldo|Reconoce la fuente|Remite a lecturas/,
      )
      .first(),
  ).toBeVisible();
  const screenshot = process.env.T03_OUTPUT_DIR
    ? path.join(process.env.T03_OUTPUT_DIR, `t03_ejemplo_real_${testInfo.project.name}.png`)
    : testInfo.outputPath('real-example.png');
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
  await page.screenshot({ path: screenshot, fullPage: true });
  if (process.env.T03_OUTPUT_DIR) {
    fs.writeFileSync(
      path.join(process.env.T03_OUTPUT_DIR, 't03_aceptacion_real.json'),
      JSON.stringify(
        {
          ok: true,
          paper_id: data.articulo.paper_id,
          version_contenido: data.articulo.version_contenido,
          top3_ids: data.top3.map((chunk: { chunk_id: string }) => chunk.chunk_id),
          clases: { M: data.clasificadores.M.clase, S: data.clasificadores.S.clase },
          textos_verificados_con_corpus: true,
          contexto_sintetico_sin_train_gold: true,
          servicio: process.env.E2E_BASE_URL || 'contenedor local ARM64; no despliegue AWS',
        },
        null,
        2,
      ) + '\n',
    );
  }
});
