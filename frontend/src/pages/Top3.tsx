import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, errorMessage, type Top3CorpusExample, type Top3Response, type DenseTop3Response, type DenseCorpusResponse } from '../api';
import { Icon } from '../components/Icon';
export function Top3() {
  const [context, setContext] = useState('');
  const [id, setId] = useState('');
  const [text, setText] = useState('');
  const [result, setResult] = useState<Top3Response | DenseTop3Response | DenseCorpusResponse>();
  const [retrieval, setRetrieval] = useState<'bm25' | 'scibert'>('bm25');
  const [submitted, setSubmitted] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [corpusExamples, setCorpusExamples] = useState<Top3CorpusExample[]>([]);
  const [selectedCorpusId, setSelectedCorpusId] = useState('');
  const [corpusMessage, setCorpusMessage] = useState('');
  const [resultMode, setResultMode] = useState<'manual' | 'corpus'>('manual');
  const [citedTitle, setCitedTitle] = useState('');
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
      const data = retrieval === 'scibert'
        ? await api.top3SciBERT(context.trim(), id.trim(), paragraphs, current.signal)
        : await api.top3(context.trim(), id.trim(), paragraphs, current.signal);
      if (!current.signal.aborted) {
        setResult(data);
        setResultMode('manual');
        setCitedTitle('');
        setSubmitted(JSON.stringify([context, id, text, retrieval]));
        requestAnimationFrame(() => title.current?.focus());
      }
    } catch (err) {
      if (!current.signal.aborted) setError(err instanceof ApiError && err.status === 503 && retrieval === 'scibert'
        ? 'SciBERT no está disponible: falta su snapshot verificado o el servicio de inferencia no está activado.'
        : errorMessage(err));
    } finally {
      if (!current.signal.aborted) setLoading(false);
    }
  }
  async function loadCorpusExamples() {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setLoading(true);
    setError('');
    setCorpusMessage('');
    try {
      const catalog = await api.top3CorpusExamples(current.signal);
      if (current.signal.aborted) return;
      setCorpusExamples(catalog.ejemplos);
      setSelectedCorpusId(catalog.ejemplos[0]?.context_id ?? '');
      if (!catalog.ejemplos.length) setCorpusMessage('El corpus de desarrollo no tiene casos disponibles.');
    } catch (err) {
      if (current.signal.aborted) return;
      setCorpusExamples([]);
      setSelectedCorpusId('');
      setCorpusMessage(err instanceof ApiError && err.status === 503
        ? 'El servidor no tiene instalado el artefacto de desarrollo ACL-200/ACL OCL. Usa el modo manual o genera el artefacto TRAIN.'
        : errorMessage(err));
    } finally {
      if (!current.signal.aborted) setLoading(false);
    }
  }

  async function runCorpusExample() {
    if (!selectedCorpusId) return;
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setLoading(true);
    setError('');
    setResult(undefined);
    try {
      const data = retrieval === 'scibert'
        ? await api.top3SciBERTCorpus(selectedCorpusId, current.signal)
        : await api.top3Corpus(selectedCorpusId, current.signal);
      if (current.signal.aborted) return;
      if (data.split !== 'train' || data.metodo !== (retrieval === 'scibert'
        ? 'scibert_base_mean_pooling_cosine' : 'BM25_lexico_baseline')) {
        throw new Error('La respuesta no corresponde al corpus TRAIN y baseline esperados.');
      }
      setContext(data.contexto);
      setId(data.cited_id);
      setText('');
      setCitedTitle(data.cited_title);
      setResultMode('corpus');
      setResult(data);
      setSubmitted(JSON.stringify([data.contexto, data.cited_id, '', retrieval]));
      requestAnimationFrame(() => title.current?.focus());
    } catch (err) {
      if (!current.signal.aborted) setError(err instanceof ApiError && err.status === 503 && retrieval === 'scibert'
        ? 'SciBERT no está disponible: falta su snapshot verificado o el servicio de inferencia no está activado.'
        : errorMessage(err));
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
    setResultMode('manual');
    setCitedTitle('');
  }
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">Experimental · Fragmentos de un artículo</span>
          <h1>Encuentra el fragmento que respalda tu cita.</h1>
          <p>Recupera fragmentos por BM25 léxico o por SciBERT base cuando esté instalado.</p>
        </div>
      </div>
      <p className="notice">
        Esta búsqueda usa únicamente los párrafos que aportes. No descarga artículos ni consulta
        automáticamente el corpus completo. Los puntajes BM25 y la similitud coseno no son probabilidades.
      </p>
      <section className="workspace">
        <div className="corpus-demo" aria-label="Casos reales de desarrollo">
          <h2>Probar con un caso real del corpus de desarrollo</h2>
          <p className="field-help">
            Solo ejemplos de TRAIN, provenientes de ACL-200 y ACL OCL. No incluyen
            etiquetas Gold ni validación humana de relevancia. Elige BM25 o SciBERT experimental.
          </p>
          <div className="form-actions">
            <button type="button" className="text-button" disabled={loading}
              onClick={loadCorpusExamples}>
              Cargar casos reales de desarrollo
            </button>
            {corpusExamples.length > 0 && (
              <>
                <label htmlFor="corpus-dev-case">Caso del corpus</label>
                <select id="corpus-dev-case" value={selectedCorpusId}
                  disabled={loading} onChange={(e) => setSelectedCorpusId(e.target.value)}>
                  {corpusExamples.map((c) => (
                    <option key={c.context_id} value={c.context_id}>
                      {c.cited_id} · {c.cited_title} ({c.total_chunks} chunks)
                    </option>
                  ))}
                </select>
                <button type="button" className="text-button" disabled={loading || !selectedCorpusId}
                  onClick={runCorpusExample}>
                  Ejecutar Top-3 de desarrollo
                </button>
              </>
            )}
          </div>
          {corpusMessage && <p className="field-help" role="status">{corpusMessage}</p>}
        </div>
        <form onSubmit={submit}>
          <label htmlFor="top3-method">Método de recuperación Top-3</label>
          <select id="top3-method" value={retrieval} disabled={loading}
            onChange={(e) => setRetrieval(e.target.value as 'bm25' | 'scibert')}>
            <option value="bm25">BM25 léxico (línea base)</option>
            <option value="scibert">SciBERT base semántico (requiere modelo)</option>
          </select>
          <p className="field-help">
            SciBERT necesita snapshot verificado en el backend. Su similitud coseno
            no demuestra relevancia ni calidad Gold.
          </p>
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
            <span>{result.cited_id}{resultMode === 'corpus' && citedTitle ? ` · ${citedTitle}` : ''}</span>
          </div>
          {submitted !== JSON.stringify([context, id, text, retrieval]) && (
            <p className="notice">
              Resultados de la consulta anterior. Vuelve a buscar para actualizar.
            </p>
          )}
          {resultMode === 'corpus' && (
            <p className="notice">
              Datos del artículo citado en ACL OCL · subconjunto TRAIN · {'metodo' in result && result.metodo === 'scibert_base_mean_pooling_cosine' ? 'SciBERT base' : 'BM25'}. Esta demostración no representa una evaluación Gold.
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
                    <span className="score">
                      {'puntaje_bm25' in f && typeof f.puntaje_bm25 === 'number'
                        ? `BM25 ${f.puntaje_bm25.toFixed(3)}`
                        : 'similitud_coseno' in f && typeof f.similitud_coseno === 'number'
                          ? `Coseno ${f.similitud_coseno.toFixed(3)}`
                          : 'Sin puntuación'}
                    </span>
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
          Este flujo Top-3 no genera etiquetas de función. La <a href="/funcion">vista de función de cita</a>
          ofrece un clasificador A4 provisional por entrada A cuando se instalen sus pesos verificados;
          no equivale a validación humana.
        </p>
      </section>
    </>
  );
}
