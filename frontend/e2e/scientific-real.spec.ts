import { chooseArticle, selectedArticle } from './article-picker.helpers';
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import fullCatalog from '../src/fullArticleCatalog.json' with { type: 'json' };
import initialCatalog from '../src/articleCatalog.json' with { type: 'json' };

test.skip(!process.env.LIVE_SCIENCE_E2E, 'Requiere un servicio M/S disponible.');
for (const scenario of ['initial', 'expanded', 'truncated', 'truncated_characters'] as const) {
  test(`${scenario}: completa el flujo con M/S real y textos del artículo`, async ({
    page,
  }, testInfo) => {
    test.setTimeout(120000);
    const manifest = JSON.parse(fs.readFileSync('../config/corpus_release.json', 'utf8'));
    const paperId =
      scenario === 'truncated_characters'
        ? manifest.ejemplos_recortados[4]
        : scenario === 'truncated'
          ? manifest.ejemplos_recortados[0]
          : scenario === 'initial'
            ? 'W05-0821'
            : fullCatalog.articulos.find(
                (a) =>
                  a.preparado && !initialCatalog.articulos.some((p) => p.paper_id === a.paper_id),
              )!.paper_id;
    const repo = path.resolve('..');
    const article = JSON.parse(
      execFileSync(
        path.join(repo, '.venv/bin/python'),
        [
          '-c',
          'import json,sys;from src.app.article_corpus import corpus;print(json.dumps(corpus()[0]["documentos"][sys.argv[1]]))',
          paperId,
        ],
        { cwd: repo, encoding: 'utf8' },
      ),
    );
    await page.goto('/');
    await expect(page.locator('#classifier option[value="open"]')).toHaveCount(0);
    if (scenario === 'initial') {
      await page.getByRole('button', { name: 'Usar ejemplo público' }).click();
    } else {
      await page
        .getByLabel('Contexto en inglés')
        .fill(
          'Earlier work TARGETCIT introduced methods for language processing and information retrieval.',
        );
    }
    const suggestions = page.waitForResponse((r) =>
      r.url().endsWith('/api/analisis-cita-ms/recomendar'),
    );
    await page.getByRole('button', { name: 'Siguiente: artículo', exact: true }).click();
    expect((await suggestions).status()).toBe(200);
    await expect(selectedArticle(page)).toHaveCount(0);
    await chooseArticle(page, paperId);
    await expect(page.getByText(/Texto preparado: disponible\./)).toBeVisible();
    await page.getByRole('button', { name: 'Siguiente: clasificador', exact: true }).click();
    await expect(selectedArticle(page)).toContainText(paperId);
    const responsePromise = page.waitForResponse(
      (response) => response.url().endsWith('/api/analisis-cita-ms/articulo'),
      { timeout: 60000 },
    );
    let starts = 0;
    page.on('request', (r) => {
      if (r.url().endsWith('/api/analisis-cita-ms/articulo') && r.method() === 'POST') starts++;
    });
    const resultPromise = page.waitForResponse(
      (r) => r.url().includes('/api/analisis-cita-ms/articulo/') && r.status() !== 202,
      { timeout: 100000 },
    );
    await page.getByRole('button', { name: 'Ver resultados', exact: true }).click();
    const started = await responsePromise;
    expect(started.status()).toBe(202);
    const response = await resultPromise;
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(starts).toBe(1);
    expect(data.articulo.paper_id).toBe(paperId);
    if (scenario.startsWith('truncated')) {
      expect(data.articulo.truncamiento.aplicado).toBe(true);
      expect(data.articulo.total_fragmentos).toBeLessThanOrEqual(100);
      expect(data.articulo.truncamiento.caracteres_analizados).toBeLessThanOrEqual(56000);
      if (scenario === 'truncated_characters') {
        expect(data.articulo.truncamiento.caracteres_originales).toBeGreaterThan(56000);
        expect(data.articulo.truncamiento.caracteres_analizados).toBeGreaterThan(55000);
        expect(article.candidatos.filter((c: { recortado?: boolean }) => c.recortado)).toHaveLength(
          1,
        );
        expect(article.candidatos.at(-1).recortado).toBe(true);
      }
      await expect(
        page.locator('#analysis-results').getByText(/Análisis limitado a/),
      ).toBeVisible();
    }
    expect(data.top3).toHaveLength(3);
    expect(new Set(data.top3.map((chunk: { chunk_id: string }) => chunk.chunk_id)).size).toBe(3);
    const chunks = article.candidatos;
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
      ? path.join(process.env.T03_OUTPUT_DIR, `t03_${scenario}_${testInfo.project.name}.png`)
      : testInfo.outputPath('real-example.png');
    await expect(page.locator('body')).toHaveJSProperty(
      'scrollWidth',
      await page.locator('body').evaluate((e) => e.clientWidth),
    );
    await page.screenshot({ path: screenshot, fullPage: true });
    if (process.env.T03_OUTPUT_DIR) {
      fs.writeFileSync(
        path.join(process.env.T03_OUTPUT_DIR, `t03_${scenario}_${testInfo.project.name}.json`),
        JSON.stringify(
          {
            ok: true,
            modo_asincrono: true,
            inicios_de_inferencia: starts,
            paper_id: data.articulo.paper_id,
            version_contenido: data.articulo.version_contenido,
            truncamiento: data.articulo.truncamiento,
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
}
