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

test('consulta el mismo análisis pendiente sin repetir POST', async () => {
  const { analyzeArticle } = await import('../api');
  vi.useFakeTimers();
  const id = 'a'.repeat(32);
  const pending = { estado: 'procesando', trabajo_id: id };
  const fetch = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => pending })
    .mockResolvedValueOnce({ ok: true, json: async () => pending })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ top3: [1, 2, 3] }) });
  vi.stubGlobal('fetch', fetch);
  try {
    const result = analyzeArticle(
      'Prior work TARGETCIT.',
      'W05-0821',
      new AbortController().signal,
    );
    await vi.advanceTimersByTimeAsync(2100);
    expect(await result).toEqual({ top3: [1, 2, 3] });
    expect(fetch.mock.calls.map(([path, options]) => [path, options.method || 'GET'])).toEqual([
      ['/api/analisis-cita-ms/articulo', 'POST'],
      [`/api/analisis-cita-ms/articulo/${id}`, 'GET'],
      [`/api/analisis-cita-ms/articulo/${id}`, 'GET'],
    ]);
  } finally {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});

test('un fallo de consulta no reintenta ni repite inferencia', async () => {
  const { analyzeArticle } = await import('../api');
  vi.useFakeTimers();
  const fetch = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ estado: 'procesando', trabajo_id: 'a'.repeat(32) }),
    })
    .mockResolvedValueOnce({
      ok: false,
      status: 410,
      json: async () => ({ detail: 'Análisis expirado.' }),
    });
  vi.stubGlobal('fetch', fetch);
  try {
    const result = expect(
      analyzeArticle('Prior work TARGETCIT.', 'W05-0821', new AbortController().signal),
    ).rejects.toThrow('Análisis expirado.');
    await vi.advanceTimersByTimeAsync(3000);
    await result;
    expect(fetch).toHaveBeenCalledTimes(2);
  } finally {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});

test('cancelar detiene las consultas pendientes sin repetir inferencia', async () => {
  const { analyzeArticle } = await import('../api');
  vi.useFakeTimers();
  const fetch = vi
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => ({ estado: 'procesando', trabajo_id: 'a'.repeat(32) }),
    });
  vi.stubGlobal('fetch', fetch);
  try {
    const controller = new AbortController();
    const result = expect(
      analyzeArticle('Prior work TARGETCIT.', 'W05-0821', controller.signal),
    ).rejects.toMatchObject({ name: 'AbortError' });
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await result;
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetch).toHaveBeenCalledTimes(1);
  } finally {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});
