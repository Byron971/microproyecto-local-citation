import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test.skip(!process.env.LIVE_COMMERCIAL_E2E, 'Requiere el comercial publicado y cuota disponible.');
test('ejemplo público con GPT real, consentimiento y Top-3', async ({ page }, info) => {
  test.setTimeout(100000);
  const corpus = JSON.parse(fs.readFileSync('../config/corpus_ms.json', 'utf8'));
  await page.goto('/');
  await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
  await expect(page.getByText('Texto preparado: disponible.')).toBeVisible();
  await expect(page.locator('#classifier option[value="commercial"]')).toHaveCount(1);
  await expect(page.locator('#classifier option[value="open"]')).toHaveCount(0);
  await page.getByLabel('Familia y modelo').selectOption('commercial');
  await page.getByRole('button', { name: 'Analizar cita', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Confirma el envío');
  await page.getByRole('checkbox', { name: /Acepto enviar/ }).check();
  const fragmentsPromise = page.waitForResponse(
    (r) => r.url().endsWith('/api/analisis-cita-ms/articulo'),
    { timeout: 60000 },
  );
  const commercialPromise = page.waitForResponse(
    (r) => r.url().endsWith('/api/comercial/clasificar'),
    { timeout: 80000 },
  );
  await page.getByRole('button', { name: 'Analizar cita', exact: true }).click();
  const fragmentsResponse = await fragmentsPromise;
  expect(fragmentsResponse.status()).toBe(200);
  const fragments = await fragmentsResponse.json();
  expect(fragments.top3).toHaveLength(3);
  for (const chunk of fragments.top3) {
    expect(
      corpus.documentos['W05-0821'].candidatos.find(
        (c: { chunk_id: string }) => c.chunk_id === chunk.chunk_id,
      )?.texto,
    ).toBe(chunk.texto);
    await expect(page.getByText(chunk.texto, { exact: true })).toBeVisible();
  }
  const response = await commercialPromise;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.modelo_solicitado).toBe('gpt-6.1-sol');
  expect(result.modelo_efectivo).toMatch(/^gpt-6\.1-sol/);
  expect(result.perfil).toBe('zero_shot_detailed');
  expect(result.puntuaciones).toHaveLength(9);
  const panel = page.getByRole('region', { name: 'Clasificación comercial' });
  await expect(
    panel.getByText(result.clase || result.abstencion, { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Modelo M', exact: true })).toHaveCount(0);
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.locator('body').evaluate((e) => e.clientWidth),
  );
  await page.screenshot({ path: info.outputPath('comercial-publico.png'), fullPage: true });
  fs.writeFileSync(
    info.outputPath('aceptacion-comercial.json'),
    JSON.stringify(
      {
        web: process.env.E2E_BASE_URL,
        modelo_efectivo: result.modelo_efectivo,
        perfil: result.perfil,
        clase: result.clase,
        top3: fragments.top3.map((c: { chunk_id: string }) => c.chunk_id),
        latencia_proveedor_ms: result.latencia_ms,
        textos_publicos_verificados: true,
        llamadas_comerciales: 1,
        contexto_inventado_sin_train_gold: true,
      },
      null,
      2,
    ),
  );
});
