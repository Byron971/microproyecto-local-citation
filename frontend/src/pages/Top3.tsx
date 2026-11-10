import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, errorMessage, type Top3Response } from '../api';
import { Icon } from '../components/Icon';
export function Top3() {
  const [context, setContext] = useState('');
  const [id, setId] = useState('');
  const [text, setText] = useState('');
  const [result, setResult] = useState<Top3Response>();
  const [submitted, setSubmitted] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function submit(e: FormEvent) {
    e.preventDefault();
    const paragraphs = text
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean);
    if (!context.trim() || !id.trim() || !paragraphs.length) {
      setError('Completa el contexto, el ID y al menos un párrafo.');
      return;
    }
    if (
      context.length > 4000 ||
      id.length > 120 ||
      paragraphs.length > 100 ||
      paragraphs.some((p) => p.length > 5000) ||
      context.length + paragraphs.join('').length > 60000
    ) {
      setError('Usa hasta 100 párrafos de 5.000 caracteres y 60.000 caracteres en total.');
      return;
    }
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setError('');
    setLoading(true);
    setResult(undefined);
    try {
      const data = await api.top3(context.trim(), id.trim(), paragraphs, current.signal);
      if (!current.signal.aborted) {
        setResult(data);
        setSubmitted(JSON.stringify([context, id, text]));
        requestAnimationFrame(() => title.current?.focus());
      }
    } catch (err) {
      if (!current.signal.aborted) setError(errorMessage(err));
    } finally {
      if (!current.signal.aborted) setLoading(false);
    }
  }
  function example() {
    setContext('Graph neural networks learn distributed representations TARGETCIT.');
    setId('ejemplo-sintetico');
    setText(
      'Graph neural networks learn representations of nodes and edges.\n\nMachine translation evaluation compares translated sentences.\n\nDistributed graph representations improve node classification.',
    );
    setResult(undefined);
  }
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">Experimental · Fragmentos de un artículo</span>
          <h1>Encuentra el fragmento que respalda tu cita.</h1>
          <p>Compara tu contexto con párrafos del mismo artículo. Recuperación léxica BM25.</p>
        </div>
      </div>
      <p className="notice">
        Esta búsqueda usa únicamente los párrafos que aportes. No descarga artículos ni consulta
        automáticamente el corpus completo. Los puntajes BM25 no son probabilidades.
      </p>
      <section className="workspace">
        <form onSubmit={submit}>
          <label htmlFor="fragment-context">Contexto de cita (en inglés)</label>
          <textarea
            id="fragment-context"
            lang="en"
            rows={3}
            maxLength={4000}
            value={context}
            onChange={(e) => setContext(e.target.value)}
          />
          <label htmlFor="cited-id">ID del artículo citado</label>
          <input
            id="cited-id"
            value={id}
            maxLength={120}
            onChange={(e) => setId(e.target.value)}
            placeholder="P14-1011"
          />
          <label htmlFor="paragraphs">Párrafos del mismo artículo</label>
          <p className="field-help" id="paragraph-help">
            Sepáralos con una línea en blanco. Hasta 100 párrafos.
          </p>
          <textarea
            id="paragraphs"
            lang="en"
            rows={8}
            value={text}
            aria-describedby="paragraph-help"
            onChange={(e) => setText(e.target.value)}
          />
          <div className="form-actions">
            <button className="primary" disabled={loading}>
              <Icon name="search" size={20} />
              {loading ? 'Buscando…' : 'Buscar evidencia Top-3'}
            </button>
            <button type="button" className="text-button" onClick={example}>
              Usar ejemplo sintético
            </button>
          </div>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>
      {result && (
        <section className="results-section">
          <div className="section-heading">
            <h2 ref={title} tabIndex={-1}>
              Fragmentos recuperados{' '}
              <span className="result-count">{result.fragmentos.length}</span>
            </h2>
            <span>{result.cited_id}</span>
          </div>
          {submitted !== JSON.stringify([context, id, text]) && (
            <p className="notice">
              Resultados de la consulta anterior. Vuelve a buscar para actualizar.
            </p>
          )}
          {!result.fragmentos.length ? (
            <p>No hay coincidencias léxicas suficientes. No se inventaron fragmentos.</p>
          ) : (
            <ol className="fragment-list">
              {result.fragmentos.map((f) => (
                <li key={f.chunk_id}>
                  <div>
                    <span className="eyebrow">
                      {f.chunk_id}
                      {f.seccion ? ` · ${f.seccion}` : ''}
                    </span>
                    <span className="score">BM25 {f.puntaje_bm25.toFixed(3)}</span>
                  </div>
                  <p lang="en">{f.texto}</p>
                </li>
              ))}
            </ol>
          )}
          <p className="field-help">
            Se analizaron {result.total_fragmentos_analizados} fragmentos del artículo indicado.
          </p>
        </section>
      )}
      <section className="classification-state">
        <span className="eyebrow">Función de cita</span>
        <h2>Clasificación aún no disponible</h2>
        <p>
          No hay un clasificador de nueve funciones integrado y validado. La recuperación Top-3
          funciona de forma independiente; no genera etiquetas de función de cita.
        </p>
      </section>
    </>
  );
}
