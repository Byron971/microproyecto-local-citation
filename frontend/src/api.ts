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

export type JobState =
  'en_cola' | 'procesando' | 'completado' | 'fallido' | 'expirado' | 'cancelado';
export interface AnalysisJob<T> {
  trabajo_id: string;
  estado: JobState;
  creado_en: number;
  espera_maxima_s: number;
  retencion_s: number;
  reintentando?: boolean;
  resultado?: T;
  error?: { codigo: string; mensaje: string };
}
const STATES: JobState[] = [
  'en_cola',
  'procesando',
  'completado',
  'fallido',
  'expirado',
  'cancelado',
];
const JOB_ID = /^[a-f0-9]{32}$/;
export const isTerminal = (state: JobState) => !['en_cola', 'procesando'].includes(state);

export function newIdempotencyKey(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

function checkJob<T>(job: AnalysisJob<T>, id?: string): AnalysisJob<T> {
  if (
    !job ||
    !JOB_ID.test(job.trabajo_id) ||
    (id !== undefined && job.trabajo_id !== id) ||
    !STATES.includes(job.estado) ||
    (job.estado === 'completado' && !job.resultado)
  )
    throw new ApiError('El servidor devolvió un estado de análisis inválido.', 502);
  return job;
}

// One POST admits one analysis; the same key never starts a second one.
export async function startAnalysisJob<T>(
  contexto: string,
  paper_id: string,
  clave_idempotencia: string,
  signal: AbortSignal,
): Promise<AnalysisJob<T>> {
  const job = await request<AnalysisJob<T>>('/api/analisis-cita-ms/trabajos', {
    method: 'POST',
    signal,
    body: JSON.stringify({ contexto, paper_id, clave_idempotencia }),
  });
  return checkJob(job);
}

export async function readAnalysisJob<T>(id: string, signal: AbortSignal): Promise<AnalysisJob<T>> {
  if (!JOB_ID.test(id)) throw new ApiError('Identificador de análisis inválido.', 400);
  return checkJob(
    await request<AnalysisJob<T>>(`/api/analisis-cita-ms/trabajos/${id}`, { signal }),
    id,
  );
}

export async function cancelAnalysisJob(id: string): Promise<AnalysisJob<unknown>> {
  const job = await request<AnalysisJob<unknown>>(`/api/analisis-cita-ms/trabajos/${id}/cancelar`, {
    method: 'POST',
  });
  return checkJob(job, id);
}

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException('Cancelado', 'AbortError'));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', abort);
      resolve();
    }, ms);
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
  });
}

// A request timeout is transient; only the caller's own cancellation stops following.
const transient = (error: unknown, signal: AbortSignal) =>
  !signal.aborted && (!(error instanceof ApiError) || [429, 502, 503, 504].includes(error.status));

// GETs only observe the job; transient read failures are retried, never the POST.
export async function followAnalysisJob<T>(
  initial: AnalysisJob<T>,
  signal: AbortSignal,
  onUpdate: (job: AnalysisJob<T>) => void,
): Promise<AnalysisJob<T>> {
  let job = checkJob(initial);
  const started = Date.now();
  // Server-side expiry is authoritative; this only bounds a client that cannot reach it.
  const deadline = started + (job.espera_maxima_s + 600) * 1000;
  let failures = 0;
  while (!isTerminal(job.estado)) {
    if (Date.now() >= deadline)
      throw new ApiError(
        'El análisis sigue pendiente. Tu contexto se conserva; recarga la página para consultarlo de nuevo.',
        504,
      );
    await wait(Date.now() - started < 30000 ? 2000 : 5000, signal);
    try {
      const next = checkJob(
        await request<AnalysisJob<T>>(`/api/analisis-cita-ms/trabajos/${job.trabajo_id}`, {
          signal,
        }),
        job.trabajo_id,
      );
      failures = 0;
      if (next.estado !== job.estado || next.reintentando !== job.reintentando) onUpdate(next);
      job = next;
    } catch (error) {
      if (!transient(error, signal) || ++failures >= 5) throw error;
    }
  }
  return job;
}
