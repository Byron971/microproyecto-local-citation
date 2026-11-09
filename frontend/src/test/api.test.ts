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
