export interface Model {
  id: string;
  nombre: string;
  descripcion: string;
  disponible: boolean;
  motivo: string | null;
  puntaje: { etiqueta: string; descripcion: string };
  devuelve_tfidf: boolean;
}
export interface Catalog {
  predeterminado: string;
  modelos: Model[];
}
export interface Recommendation {
  posicion: number;
  paper_id: string;
  titulo: string;
  resumen: string;
  similitud: number;
  similitud_tfidf?: number;
}
export interface RecommendationResponse {
  consulta: string;
  modelo?: string;
  total: number;
  recomendaciones: Recommendation[];
}
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
export interface Fragment {
  posicion: number;
  chunk_id: string;
  texto: string;
  seccion?: string;
  puntaje_bm25: number;
}
export interface Top3Response {
  cited_id: string;
  total_fragmentos_analizados: number;
  fragmentos: Fragment[];
  clasificacion: { estado: string; motivo?: string };
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
  const timeout = setTimeout(() => controller.abort(), 32_000);
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
export const api = {
  reference: (paperId: string, signal?: AbortSignal) =>
    request<{ paper_id: string; bibtex: string; source_url: string }>(
      `/api/referencias/${encodeURIComponent(paperId)}`,
      { signal },
    ),
  examples: (signal?: AbortSignal) => request<ExamplesCatalog>('/api/ejemplos', { signal }),
  status: (signal?: AbortSignal) =>
    request<{ listo: boolean; modelo: Record<string, unknown> }>('/api/estado', { signal }),
  models: (signal?: AbortSignal) => request<Catalog>('/api/modelos', { signal }),
  example: (signal?: AbortSignal) => request<Example>('/api/ejemplo', { signal }),
  recommend: (contexto: string, top_k: number, modelo?: string, signal?: AbortSignal) =>
    request<RecommendationResponse>('/api/recomendar', {
      method: 'POST',
      body: JSON.stringify({ contexto, top_k, ...(modelo ? { modelo } : {}) }),
      signal,
    }),
  top3: (contexto: string, cited_id: string, paragraphs: string[], signal?: AbortSignal) =>
    request<Top3Response>('/api/top3-fragmentos', {
      method: 'POST',
      body: JSON.stringify({
        contexto,
        cited_id,
        parrafos: paragraphs.map((texto, i) => ({ chunk_id: `p${i + 1}`, texto })),
      }),
      signal,
    }),
};
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
