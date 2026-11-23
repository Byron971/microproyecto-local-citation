export interface Example {
  texto: string;
  cita_correcta: string;
  titulo_correcto: string;
}
export interface ExamplesCatalog {
  total: number;
  particion: string | null;
  ejemplos: (Example & { context_id: string })[];
}
export interface DenseFragment {
  posicion: number;
  chunk_id: string;
  texto: string;
  seccion?: string | null;
  paragraph_indices?: number[];
  similitud_coseno: number;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  // API Gateway responde o vence a los 30 s; dejar margen de transporte.
  const timeoutMs = 32_000;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const forwardAbort = () => controller.abort();
  options.signal?.addEventListener('abort', forwardAbort, { once: true });
  if (options.signal?.aborted) controller.abort();
  try {
    const response = await fetch(`${base}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = data?.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((e: { msg: string }) => e.msg).join('. ')
            : `El servidor respondió ${response.status}.`;
      throw new ApiError(message, response.status);
    }
    if (data === null)
      throw new ApiError('El servidor no devolvió una respuesta válida.', response.status);
    return data as T;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', forwardAbort);
  }
}
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503)
      return 'El servicio no está disponible todavía. Inténtalo en unos segundos.';
    if ([404, 409].includes(error.status)) return error.message;
    return error.message;
  }
  if (error instanceof DOMException && error.name === 'AbortError')
    return 'La consulta tardó demasiado. Vuelve a intentarlo.';
  return 'No se pudo conectar con el servidor. Comprueba la conexión e inténtalo de nuevo.';
}

// One POST starts one analysis. GETs only observe that execution, never retry it.
export async function analyzeArticle<T>(
  contexto: string,
  paper_id: string,
  signal: AbortSignal,
): Promise<T> {
  type Pending = { estado: 'procesando'; trabajo_id: string };
  let result = await request<T | Pending>('/api/analisis-cita-ms/articulo', {
    method: 'POST',
    signal,
    body: JSON.stringify({ contexto, paper_id, asincrono: true }),
  });
  const started = Date.now();
  let id: string | undefined;
  while (result && typeof result === 'object' && 'trabajo_id' in result) {
    const pending = result as Pending;
    if (
      pending.estado !== 'procesando' ||
      !/^[a-f0-9]{32}$/.test(pending.trabajo_id) ||
      (id && id !== pending.trabajo_id)
    )
      throw new ApiError('El servidor devolvió un análisis pendiente inválido.', 502);
    id = pending.trabajo_id;
    if (Date.now() - started >= 180000)
      throw new ApiError(
        'El análisis tardó demasiado. Tu contexto se conserva; no se repitió la inferencia.',
        504,
      );
    await new Promise<void>((resolve, reject) => {
      const abort = () => {
        clearTimeout(timer);
        signal.removeEventListener('abort', abort);
        reject(new DOMException('Cancelado', 'AbortError'));
      };
      const timer = setTimeout(() => {
        signal.removeEventListener('abort', abort);
        resolve();
      }, 1000);
      signal.addEventListener('abort', abort, { once: true });
      if (signal.aborted) abort();
    });
    result = await request<T | Pending>(`/api/analisis-cita-ms/articulo/${id}`, { signal });
  }
  return result as T;
}
