import { request, ApiError } from '../api';

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

const id = 'a'.repeat(32);
const job = (estado: string, extra = {}) => ({
  trabajo_id: id,
  estado,
  creado_en: 1,
  espera_maxima_s: 900,
  retencion_s: 3600,
  ...extra,
});
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
const fail = (status: number, detail = 'Error') => ({
  ok: false,
  status,
  json: async () => ({ detail }),
});
const calls = (fetch: ReturnType<typeof vi.fn>) =>
  fetch.mock.calls.map(([path, options]) => [path, options.method || 'GET']);

test('una admisión con clave y solo consultas GET hasta completar', async () => {
  const { startAnalysisJob, followAnalysisJob } = await import('../api');
  vi.useFakeTimers();
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(ok(job('en_cola')))
    .mockResolvedValueOnce(ok(job('en_cola')))
    .mockResolvedValueOnce(ok(job('procesando')))
    .mockResolvedValueOnce(ok(job('completado', { resultado: { top3: [1, 2, 3] } })));
  vi.stubGlobal('fetch', fetch);
  try {
    const signal = new AbortController().signal;
    const first = await startAnalysisJob(
      'Prior work TARGETCIT.',
      'W05-0821',
      'clave-0000-0000-0001',
      signal,
    );
    const updates: string[] = [];
    const final = followAnalysisJob(first, signal, (next) => updates.push(next.estado));
    await vi.advanceTimersByTimeAsync(6100);
    expect((await final).resultado).toEqual({ top3: [1, 2, 3] });
    expect(updates).toEqual(['procesando', 'completado']); // Sin avisos repetidos.
    expect(JSON.parse(fetch.mock.calls[0][1].body).clave_idempotencia).toBe('clave-0000-0000-0001');
    expect(calls(fetch)).toEqual([
      ['/api/analisis-cita-ms/trabajos', 'POST'],
      [`/api/analisis-cita-ms/trabajos/${id}`, 'GET'],
      [`/api/analisis-cita-ms/trabajos/${id}`, 'GET'],
      [`/api/analisis-cita-ms/trabajos/${id}`, 'GET'],
    ]);
  } finally {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});

test('fallos transitorios de consulta se reintentan sin repetir la admisión', async () => {
  const { followAnalysisJob } = await import('../api');
  vi.useFakeTimers();
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new TypeError('red'))
    .mockResolvedValueOnce(fail(503))
    .mockResolvedValueOnce(
      ok(job('fallido', { error: { codigo: 'reinicio', mensaje: 'Reinicio' } })),
    );
  vi.stubGlobal('fetch', fetch);
  try {
    const final = followAnalysisJob(
      job('en_cola') as never,
      new AbortController().signal,
      () => {},
    );
    await vi.advanceTimersByTimeAsync(6100);
    expect((await final).estado).toBe('fallido');
    expect(calls(fetch).every(([, method]) => method === 'GET')).toBe(true);
  } finally {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});

test('un 404 de consulta es terminal y no reintenta', async () => {
  const { followAnalysisJob } = await import('../api');
  vi.useFakeTimers();
  const fetch = vi
    .fn()
    .mockResolvedValue(fail(404, 'El análisis no existe o ya no está disponible.'));
  vi.stubGlobal('fetch', fetch);
  try {
    const result = expect(
      followAnalysisJob(job('procesando') as never, new AbortController().signal, () => {}),
    ).rejects.toThrow('ya no está disponible');
    await vi.advanceTimersByTimeAsync(2100);
    await result;
    expect(fetch).toHaveBeenCalledTimes(1);
  } finally {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});

test('abandonar la espera detiene las consultas', async () => {
  const { followAnalysisJob } = await import('../api');
  vi.useFakeTimers();
  const fetch = vi.fn().mockResolvedValue(ok(job('en_cola')));
  vi.stubGlobal('fetch', fetch);
  try {
    const controller = new AbortController();
    const result = expect(
      followAnalysisJob(job('en_cola') as never, controller.signal, () => {}),
    ).rejects.toMatchObject({ name: 'AbortError' });
    controller.abort();
    await result;
    await vi.advanceTimersByTimeAsync(10000);
    expect(fetch).not.toHaveBeenCalled();
  } finally {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  }
});

test('rechaza estados inválidos o de otro trabajo', async () => {
  const { readAnalysisJob } = await import('../api');
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(ok({ ...job('completado'), trabajo_id: 'b'.repeat(32) })),
  );
  try {
    await expect(readAnalysisJob(id, new AbortController().signal)).rejects.toThrow('inválido');
    await expect(readAnalysisJob('../x', new AbortController().signal)).rejects.toThrow('inválido');
  } finally {
    vi.unstubAllGlobals();
  }
});
