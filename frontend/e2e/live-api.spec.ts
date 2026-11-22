import { test, expect } from '@playwright/test';

// Este archivo solo se ejecuta con un backend FastAPI REAL levantado en CI.
// Compatibilidad de las rutas baseline históricas; no prueba la búsqueda de la portada.
// La aceptación científica real está en scripts/probar_flujo_integrado_ms.py.
test.skip(!process.env.LIVE_API_E2E, 'El smoke real requiere LIVE_API_E2E=1 y FastAPI.');

test('React + FastAPI + modelo empaquetado + BM25 responden sin mocks', async ({
  page,
  request,
}) => {
  const state = await request.get('http://127.0.0.1:8000/api/estado');
  expect(state.ok()).toBeTruthy();
  const ready = await state.json();
  expect(ready.listo).toBe(true);
  expect(ready.configuracion.top3).toBe('bm25_lexical');

  const features = await request.get('http://127.0.0.1:8000/api/capacidades');
  expect(features.ok()).toBeTruthy();
  const capabilities = await features.json();
  expect(capabilities.tareas.recomendacion_articulos_tfidf.disponible).toBe(true);
  expect(capabilities.tareas.top3_manual_bm25.disponible).toBe(true);
  expect(capabilities.tareas.top3_scibert.disponible).toBe(false);
  expect(capabilities.tareas.clasificacion_nueve_funciones.disponible).toBe(false);

  const suggestion = await request.post('http://127.0.0.1:8000/api/recomendar', {
    data: {
      contexto: 'Graph representation learning improves language model performance.',
      top_k: 3,
    },
  });
  expect(suggestion.ok()).toBeTruthy();
  const recommended = await suggestion.json();
  expect(recommended.modelo).toBe('tfidf_reranker_v1');
  expect(recommended.recomendaciones.length).toBeGreaterThan(0);

  await page.goto('/fragmentos');
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('heading', { name: 'Analizar una cita' })).toBeVisible();
});
