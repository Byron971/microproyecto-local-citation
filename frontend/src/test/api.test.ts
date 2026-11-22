import { request, ApiError, api } from '../api';

test('Recomendar y catálogo utilizan SciBERT sin recurrir al recomendador anterior', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal('fetch', fetch);
  await api.models();
  await api.recommend('scientific context', 5);
  expect(fetch.mock.calls[0][0]).toContain('/api/analisis-cita-ms/modelos');
  expect(fetch.mock.calls[1][0]).toContain('/api/analisis-cita-ms/recomendar');
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    contexto: 'scientific context',
    top_k: 5,
  });
  vi.unstubAllGlobals();
});
test('convierte los errores de validación 422 en un mensaje legible', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{ msg: 'Debe ser un entero' }, { msg: 'Valor fuera de rango' }],
      }),
    }),
  );
  await expect(request('/api/recomendar')).rejects.toThrow(
    'Debe ser un entero. Valor fuera de rango',
  );
  vi.unstubAllGlobals();
});
test('no trata HTML exitoso como datos del API', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new Error('HTML');
      },
    }),
  );
  await expect(request('/api/estado')).rejects.toBeInstanceOf(ApiError);
  vi.unstubAllGlobals();
});
