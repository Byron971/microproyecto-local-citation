import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, errorMessage, type FunctionBResponse, type Top3CorpusExample } from '../api';

/** Modelo A4-B: SciBERT Top-3 REAL, perfiles de sección y nueve funciones. */
export function CitationFunctionB() {
  const [context, setContext] = useState('');
  const [cited, setCited] = useState('');
  const [paragraphs, setParagraphs] = useState('');
  const [examples, setExamples] = useState<Top3CorpusExample[]>([]);
  const [chosen, setChosen] = useState('');
  const [result, setResult] = useState<FunctionBResponse>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function runManual(e: FormEvent) {
    e.preventDefault();
    const chunks = paragraphs.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
    if (context.split('TARGETCIT').length !== 2 || !cited.trim() || chunks.length < 3
        || chunks.length > 100 || chunks.some(p => p.length > 5000)
        || context.length + chunks.join('').length > 60000) {
      setError('Se requiere un TARGETCIT, ID del citado y entre 3 y 100 párrafos válidos.');
      return;
    }
    await execute(signal => api.classifyCitationB(context.trim(), cited.trim(), chunks, signal));
  }

  async function loadExamples() {
    await execute(async signal => {
      const catalog = await api.top3CorpusExamples(signal);
      setExamples(catalog.ejemplos);
      setChosen(catalog.ejemplos[0]?.context_id ?? '');
      return null;
    });
  }

  async function runCorpus() {
    if (!chosen) return;
    await execute(signal => api.classifyCitationBCorpus(chosen, signal));
  }

  async function execute(fn: (signal: AbortSignal) => Promise<FunctionBResponse | null>) {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setBusy(true); setError(''); setResult(undefined);
    try {
      const answer = await fn(current.signal);
      if (current.signal.aborted || answer === null) return;
      if (answer.recuperacion.metodo !== 'scibert_base_mean_pooling_cosine'
          || answer.recuperacion.fragmentos.length !== 3
          || answer.clasificacion.entrada !== 'B'
          || answer.clasificacion.puntuaciones_softmax.length !== 9
          || answer.clasificacion.validacion !== 'provisional_no_gold_humano'
          || answer.gold_certificado !== false) {
        throw new Error('El backend no confirmó el flujo científico provisional Top-3 → A4-B.');
      }
      setResult(answer);
    } catch (err) {
      if (current.signal.aborted) return;
      setError(err instanceof ApiError && err.status === 503
        ? 'SciBERT y el checkpoint A4-B deben estar cargados y verificados. No hay sustitución por BM25.'
        : errorMessage(err));
    } finally {
      if (!current.signal.aborted) setBusy(false);
    }
  }

  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">Experimental · Recuperación + función retórica</span>
          <h1>Top-3 SciBERT y clasificación B</h1>
          <p>La entrada B utiliza exactamente tres fragmentos y sus perfiles de sección.</p>
        </div>
      </div>
      <p className="notice" role="note">
        Los resultados son provisionales: etiquetas Haiku, softmax no calibrado y
        ninguna validación con Test Gold humano. Los casos manuales requieren
        aportar fragmentos del artículo citado; la API no verifica su identidad documental.
      </p>
      <section className="workspace">
        <div className="corpus-demo" aria-label="Ejemplos TRAIN sin Gold">
          <h2>Prueba con un artículo citado auténtico de TRAIN</h2>
          <button type="button" className="text-button" disabled={busy} onClick={loadExamples}>
            Cargar ejemplos de desarrollo
          </button>
          {examples.length > 0 && (
            <>
              <label htmlFor="function-b-case">Caso de desarrollo</label>
              <select id="function-b-case" value={chosen} disabled={busy}
                onChange={e => setChosen(e.target.value)}>
                {examples.map(e => (
                  <option value={e.context_id} key={e.context_id}>
                    {e.cited_id} · {e.cited_title}
                  </option>
                ))}
              </select>
              <button type="button" className="text-button" disabled={busy || !chosen}
                onClick={runCorpus}>Clasificar cita B de TRAIN</button>
            </>
          )}
        </div>
        <form onSubmit={runManual}>
          <h2>O ingresa los fragmentos manualmente</h2>
          <label htmlFor="function-b-context">Contexto con TARGETCIT</label>
          <textarea id="function-b-context" lang="en" maxLength={4000}
            value={context} onChange={e => setContext(e.target.value)} rows={3}/>
          <label htmlFor="function-b-paper">ID del artículo citado</label>
          <input id="function-b-paper" maxLength={120} value={cited}
            onChange={e => setCited(e.target.value)}/>
          <label htmlFor="function-b-paragraphs">Párrafos del citado (al menos tres)</label>
          <textarea id="function-b-paragraphs" lang="en" rows={8}
            value={paragraphs} onChange={e => setParagraphs(e.target.value)}
            placeholder={'Graph methods are useful.\n\nExperiments compare embeddings.\n\nThe work describes scientific citations.'}/>
          <div className="form-actions">
            <button type="submit" className="primary" disabled={busy}>
              {busy ? 'Procesando…' : 'Recuperar Top-3 y clasificar B'}
            </button>
          </div>
        </form>
        {error && <p className="error-message" role="alert">{error}</p>}
      </section>
      {result && (
        <section className="results-section" aria-label="Resultado B provisional">
          <div className="section-heading">
            <h2>Función estimada: {result.clasificacion.clase}</h2>
            <span>{result.clasificacion.modelo} · Entrada B</span>
          </div>
          <p className="notice">Resultado provisional Haiku. No validado sobre Gold humano.</p>
          <h3>Fragmentos SciBERT recuperados</h3>
          <ol className="fragment-list">
            {result.recuperacion.fragmentos.map(f => (
              <li key={f.chunk_id}>
                <strong>{f.chunk_id} · {f.seccion ?? 'Sin sección'} · coseno {f.similitud_coseno.toFixed(3)}</strong>
                <p>{f.texto}</p>
              </li>
            ))}
          </ol>
          <h3>Nueve puntuaciones softmax sin calibración</h3>
          <ol className="fragment-list">
            {result.clasificacion.puntuaciones_softmax.map(p => (
              <li key={p.categoria}>{p.categoria}: {p.score.toFixed(3)}</li>
            ))}
          </ol>
        </section>
      )}
    </>
  );
}
