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
  total_catalogo?: number;
  version_indice?: string;
  revision_scibert?: string;
  aviso?: string;
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
export interface Top3CorpusExample {
  context_id: string;
  cited_id: string;
  cited_title: string;
  total_chunks: number;
}
export interface Top3CorpusCatalog {
  total: number;
  ejemplos: Top3CorpusExample[];
}
export interface Top3CorpusResponse extends Top3Response {
  context_id: string;
  contexto: string;
  cited_title: string;
  split: 'train';
  fuente: string;
  metodo: string;
  aviso: string;
  sha256_ocl_citado: string;
}
export interface DenseFragment {
  posicion: number;
  chunk_id: string;
  texto: string;
  seccion?: string | null;
  paragraph_indices?: number[];
  similitud_coseno: number;
}
export interface DenseTop3Response {
  cited_id: string;
  metodo: 'scibert_base_mean_pooling_cosine';
  modelo: string;
  revision: string;
  total_fragmentos_analizados: number;
  fragmentos: DenseFragment[];
  clasificacion: { estado: string; motivo?: string };
}
export interface DenseCorpusResponse extends DenseTop3Response {
  context_id: string;
  contexto: string;
  cited_title: string;
  split: 'train';
  fuente: string;
  aviso: string;
}
export interface ClassificationResponse {
  modelo: string;
  encoder: string;
  entrada: 'A';
  clase: string;
  indice_clase: number;
  puntuaciones_softmax: { categoria: string; score: number }[];
  latencia_modelo_ms: number;
  training_labels: 'Haiku';
  validacion: 'provisional_no_gold_humano';
  advertencia: string;
}
export interface FunctionBResponse {
  context_id: string | null;
  cited_id: string;
  recuperacion: {
    metodo: 'scibert_base_mean_pooling_cosine';
    modelo: string;
    revision: string;
    fragmentos: DenseFragment[];
  };
  clasificacion: Omit<ClassificationResponse, 'entrada'> & { entrada: 'B' };
  split: 'train' | null;
  gold_certificado: false;
  aviso: string;
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
export const api = {
  reference: (paperId: string, signal?: AbortSignal) =>
    request<{ paper_id: string; bibtex: string; source_url: string }>(
      `/api/referencias/${encodeURIComponent(paperId)}`,
      { signal },
    ),
  examples: (signal?: AbortSignal) => request<ExamplesCatalog>('/api/ejemplos', { signal }),
  status: (signal?: AbortSignal) =>
    request<{ listo: boolean; modelo: Record<string, unknown> }>('/api/estado', { signal }),
  models: (signal?: AbortSignal) => request<Catalog>('/api/analisis-cita-ms/modelos', { signal }),
  example: (signal?: AbortSignal) => request<Example>('/api/ejemplo', { signal }),
  recommend: (contexto: string, top_k: number, modelo?: string, signal?: AbortSignal) =>
    request<RecommendationResponse>('/api/analisis-cita-ms/recomendar', {
      method: 'POST',
      body: JSON.stringify({ contexto, top_k, ...(modelo ? { modelo } : {}) }),
      signal,
    }),
  classifyCitationB: (
    contexto: string,
    cited_id: string,
    paragraphs: string[],
    signal?: AbortSignal,
  ) =>
    request<FunctionBResponse>('/api/clasificar-cita-b', {
      method: 'POST',
      body: JSON.stringify({
        contexto,
        cited_id,
        parrafos: paragraphs.map((texto, i) => ({ chunk_id: `p${i + 1}`, texto })),
      }),
      signal,
    }),
  classifyCitationBCorpus: (contextId: string, signal?: AbortSignal) =>
    request<FunctionBResponse>(`/api/clasificar-cita-b/corpus/${encodeURIComponent(contextId)}`, {
      signal,
    }),
  classifyCitation: (
    contexto: string,
    cited_title: string,
    cited_abstract: string,
    signal?: AbortSignal,
  ) =>
    request<ClassificationResponse>('/api/clasificar-cita', {
      method: 'POST',
      body: JSON.stringify({ contexto, cited_title, cited_abstract }),
      signal,
    }),
  classifyCitationSpecterA: (
    contexto: string,
    cited_title: string,
    cited_abstract: string,
    signal?: AbortSignal,
  ) =>
    request<ClassificationResponse>('/api/clasificar-cita-specter-a', {
      method: 'POST',
      body: JSON.stringify({ contexto, cited_title, cited_abstract }),
      signal,
    }),
  classifyCitationSpecterB: (
    contexto: string,
    cited_id: string,
    paragraphs: string[],
    signal?: AbortSignal,
  ) =>
    request<FunctionBResponse>('/api/clasificar-cita-specter-b', {
      method: 'POST',
      body: JSON.stringify({
        contexto,
        cited_id,
        parrafos: paragraphs.map((texto, i) => ({ chunk_id: `p${i + 1}`, texto })),
      }),
      signal,
    }),
  classifyCitationSpecterBCorpus: (contextId: string, signal?: AbortSignal) =>
    request<FunctionBResponse>(
      `/api/clasificar-cita-specter-b/corpus/${encodeURIComponent(contextId)}`,
      { signal },
    ),
  top3SciBERT: (contexto: string, cited_id: string, paragraphs: string[], signal?: AbortSignal) =>
    request<DenseTop3Response>('/api/top3-scibert', {
      method: 'POST',
      body: JSON.stringify({
        contexto,
        cited_id,
        parrafos: paragraphs.map((texto, i) => ({ chunk_id: `p${i + 1}`, texto })),
      }),
      signal,
    }),
  top3SciBERTCorpus: (contextId: string, signal?: AbortSignal) =>
    request<DenseCorpusResponse>(`/api/top3-scibert/corpus/${encodeURIComponent(contextId)}`, {
      signal,
    }),
  top3CorpusExamples: (signal?: AbortSignal) =>
    request<Top3CorpusCatalog>('/api/top3-corpus/ejemplos', { signal }),
  top3Corpus: (contextId: string, signal?: AbortSignal) =>
    request<Top3CorpusResponse>(`/api/top3-corpus/${encodeURIComponent(contextId)}`, { signal }),
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
