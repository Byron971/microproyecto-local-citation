import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, errorMessage, request } from '../api';
import { ScientificResults, type Respuesta } from '../components/ScientificResults';
import catalog from '../articleCatalog.json';
import datasetExamples from '../scientificExamples.json';
import { ExampleDialog } from '../components/ExampleDialog';
import type { CommercialClassification } from '../components/CommercialResults';

export const PUBLIC_EXAMPLE = {
  paperId: 'W05-0821',
  target: '[1]',
  context:
    'We use the language modeling approach described in TARGETCIT to improve a statistical machine translation system.',
};
type Analysis = Respuesta & {
  articulo: {
    paper_id: string;
    titulo: string;
    publicacion: string;
    fuente?: string;
    licencia?: string;
    version_contenido?: string;
  };
};
type Coverage = {
  paperId: string;
  status: 'checking' | 'available' | 'missing' | 'error';
  version?: string;
};

export function ScientificAnalysis() {
  const [context, setContext] = useState('');
  const [paperId, setPaperId] = useState('');
  const [variant, setVariant] = useState<'M' | 'S' | 'commercial'>('M');
  const [commercialAvailable, setCommercialAvailable] = useState(false);
  const [catalogStatus, setCatalogStatus] = useState<'checking' | 'ready' | 'error'>('checking');
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [consent, setConsent] = useState(false);
  const [commercialResult, setCommercialResult] = useState<CommercialClassification>();
  const [target, setTarget] = useState('');
  const [coverage, setCoverage] = useState<Coverage>();
  const [coverageRetry, setCoverageRetry] = useState(0);
  const [usingExample, setUsingExample] = useState(false);
  const [selectedExample, setSelectedExample] = useState('');
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [result, setResult] = useState<Analysis>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorField, setErrorField] = useState('');
  const [articleQuery, setArticleQuery] = useState('');
  const [phase, setPhase] = useState<'retrieving' | 'classifying'>('retrieving');
  const [duration, setDuration] = useState<number>();
  const [step, setStep] = useState(0);
  const [completed, setCompleted] = useState(false);
  const [completedSteps, setCompletedSteps] = useState(0);
  const input = useRef<HTMLTextAreaElement>(null);
  const active = useRef<AbortController | null>(null);
  const article = catalog.articulos.find((item) => item.paper_id === paperId);
  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    setCatalogStatus('checking');
    request<{ clasificadores: { id: string }[] }>('/api/clasificadores', {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          if (!Array.isArray(data.clasificadores)) throw new Error('Invalid classifier catalog');
          setCommercialAvailable(data.clasificadores.some((m) => m.id === 'commercial'));
          setCatalogStatus('ready');
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setCatalogStatus('error');
      });
    return () => controller.abort();
  }, [catalogRetry]);
  useEffect(() => {
    if (!paperId) {
      setCoverage(undefined);
      return;
    }
    const controller = new AbortController();
    setCoverage({ paperId, status: 'checking' });
    request<{ version_contenido: string; articulos: { paper_id: string; disponible: boolean }[] }>(
      '/api/analisis-cita-ms/disponibilidad',
      {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({ paper_ids: [paperId] }),
      },
    )
      .then((data) => {
        if (controller.signal.aborted) return;
        const entry = data.articulos?.find((item) => item.paper_id === paperId);
        if (!entry || typeof entry.disponible !== 'boolean' || !data.version_contenido) {
          throw new Error('Invalid coverage response');
        }
        setCoverage({
          paperId,
          status: entry.disponible ? 'available' : 'missing',
          version: data.version_contenido,
        });
      })
      .catch(() => {
        if (!controller.signal.aborted) setCoverage({ paperId, status: 'error' });
      });
    return () => controller.abort();
  }, [paperId, coverageRetry]);
  const coverageStatus = coverage?.paperId === paperId ? coverage.status : 'checking';

  const markerCount = context.split('TARGETCIT').length - 1;
  const contextReady =
    markerCount === 1 &&
    context.length <= 4000 &&
    context.replace('TARGETCIT', '').trim().length > 0;
  const normalize = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  const filteredArticles = catalog.articulos.filter((item) =>
    normalize(`${item.titulo} ${item.paper_id}`).includes(normalize(articleQuery).trim()),
  );
  const articleOptions =
    article && !filteredArticles.includes(article)
      ? [article, ...filteredArticles]
      : filteredArticles;
  const guidance =
    step === 2 && coverageStatus !== 'available'
      ? 'Vuelve al artículo citado para comprobar su disponibilidad.'
      : '';
  function goToStep(next: number) {
    if (
      loading ||
      (!completed && next > step + 1) ||
      (next >= 1 && !contextReady) ||
      (next >= 2 && (!article || coverageStatus !== 'available')) ||
      (next === 3 && !result)
    )
      return;
    setError('');
    setErrorField('');
    setStep(next);
    setCompletedSteps((count) => Math.max(count, next));
  }
  useEffect(() => {
    document.getElementById(`workflow-title-${step}`)?.focus();
  }, [step]);
  function submitStep(event: FormEvent) {
    event.preventDefault();
    if (step === 0 && contextReady) goToStep(1);
    else if (step === 1 && article && coverageStatus === 'available') goToStep(2);
    else if (step === 2) {
      if (completed) goToStep(3);
      else void run(event);
    }
  }
  function reportError(message: string, field: string) {
    setError(message);
    setErrorField(field);
    document.getElementById(field)?.focus();
  }
  useEffect(() => {
    if (loading) return;
    if (error && errorField === 'analysis-error')
      document.getElementById('analysis-error')?.focus();
    else if (step === 3 && result && !error) document.getElementById('analysis-results')?.focus();
  }, [loading, result, error, errorField, step]);

  function example() {
    resetWorkflow();
    setContext(PUBLIC_EXAMPLE.context);
    setTarget(PUBLIC_EXAMPLE.target);
    setPaperId(PUBLIC_EXAMPLE.paperId);
    setUsingExample(true);
    setSelectedExample('');
    setCoverageRetry((count) => count + 1);
  }

  function selectDatasetExample(id: string) {
    const item = datasetExamples.ejemplos.find((entry) => entry.context_id === id);
    if (!item) return;
    resetWorkflow();
    setContext(item.contexto);
    setPaperId(item.paper_id);
    setTarget('');
    setUsingExample(false);
    setSelectedExample(id);
    setExamplesOpen(false);
    setCoverageRetry((count) => count + 1);
  }

  function resetWorkflow() {
    invalidate();
    setStep(0);
    setCompletedSteps(0);
    setPaperId('');
    setCoverage(undefined);
    setArticleQuery('');
    setVariant('M');
    setTarget('');
    setUsingExample(false);
    setSelectedExample('');
  }

  function invalidate() {
    setCompleted(false);
    setCompletedSteps(Math.min(step, 2));
    active.current?.abort();
    setLoading(false);
    setResult(undefined);
    setCommercialResult(undefined);
    setConsent(false);
    setError('');
    setErrorField('');
    setDuration(undefined);
  }
  function mark() {
    const field = input.current;
    if (!field || field.selectionStart === field.selectionEnd) {
      reportError(
        'Selecciona la referencia dentro del contexto y pulsa «Marcar cita».',
        'citation-context',
      );
      return;
    }
    const selected = context.slice(field.selectionStart, field.selectionEnd);
    if (selected.includes('TARGETCIT')) {
      reportError('Selecciona la referencia original, no la marca TARGETCIT.', 'citation-context');
      return;
    }
    const before = context.slice(0, field.selectionStart).replaceAll('TARGETCIT', target);
    const after = context.slice(field.selectionEnd).replaceAll('TARGETCIT', target);
    const marked = `${before}TARGETCIT${after}`;
    if (marked.length > 4000) {
      reportError(
        'El contexto marcado debe tener como máximo 4000 caracteres.',
        'citation-context',
      );
      return;
    }
    resetWorkflow();
    setTarget(selected);
    setContext(marked);
    field.focus();
  }
  async function run(event: FormEvent) {
    event.preventDefault();
    if (loading || step !== 2) return;
    if (!context.trim() || context.replaceAll('TARGETCIT', '').trim() === '') {
      reportError('Escribe un contexto académico en inglés.', 'citation-context');
      return;
    }
    if (context.split('TARGETCIT').length !== 2 || context.length > 4000) {
      reportError(
        'Marca una sola cita en un contexto de hasta 4000 caracteres.',
        'citation-context',
      );
      return;
    }
    if (!article) {
      reportError('Selecciona el artículo citado por su título e ID.', 'cited-article');
      return;
    }
    if (coverageStatus !== 'available') {
      setError(
        coverageStatus === 'missing'
          ? 'Este artículo no tiene texto preparado. Selecciona otro artículo.'
          : 'Comprueba la disponibilidad del artículo antes de analizar.',
      );
      return;
    }
    if (variant === 'commercial' && (!commercialAvailable || !consent)) {
      reportError('Confirma el envío del texto a OpenAI antes de analizar.', 'commercial-consent');
      return;
    }
    active.current?.abort();
    setResult(undefined);
    setCommercialResult(undefined);
    setError('');
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setCompleted(false);
    setCompletedSteps(2);
    setErrorField('');
    setPhase('retrieving');
    setDuration(undefined);
    const started = performance.now();
    try {
      const data = await request<Analysis>('/api/analisis-cita-ms/articulo', {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({ contexto: context, paper_id: paperId }),
      });
      if (controller.signal.aborted) return;
      if (
        data.articulo?.paper_id !== paperId ||
        data.articulo?.version_contenido !== coverage?.version ||
        data.top3?.length !== 3 ||
        new Set(data.top3.map((chunk) => chunk.chunk_id)).size !== 3 ||
        data.clasificadores?.M?.probabilidades?.length !== 9 ||
        data.clasificadores?.S?.probabilidades?.length !== 9
      ) {
        throw new ApiError(
          'El análisis está incompleto o corresponde a otro artículo. Vuelve a intentarlo.',
          502,
        );
      }
      setResult(data);
      setStep(3);
      setCompletedSteps(3);
      if (variant === 'commercial') {
        setPhase('classifying');
        const commercial = await request<CommercialClassification>('/api/comercial/clasificar', {
          method: 'POST',
          signal: controller.signal,
          body: JSON.stringify({ contexto: context, paper_id: paperId, consentimiento: consent }),
        });
        if (controller.signal.aborted) return;
        if (
          commercial.paper_id !== paperId ||
          commercial.version_contenido !== data.articulo.version_contenido ||
          commercial.modelo_solicitado !== 'gpt-6.1-sol' ||
          !commercial.modelo_efectivo ||
          commercial.puntuaciones?.length !== 9 ||
          new Set(commercial.puntuaciones.map((p) => p.clase)).size !== 9 ||
          commercial.puntuaciones.some(
            (p) => !Number.isFinite(p.valor) || p.valor < 0 || p.valor > 1,
          ) ||
          (commercial.clase !== null &&
            !commercial.puntuaciones.some((p) => p.clase === commercial.clase))
        ) {
          throw new ApiError(
            'La clasificación comercial está incompleta. Los fragmentos se conservan.',
            502,
          );
        }
        setCommercialResult(commercial);
      }
      setCompleted(true);
      setCompletedSteps(4);
    } catch (err) {
      if (!controller.signal.aborted) {
        if (err instanceof ApiError && err.status === 404)
          setCoverage({ paperId, status: 'missing' });
        setErrorField('analysis-error');
        setError(errorMessage(err));
      }
    } finally {
      if (!controller.signal.aborted) {
        setDuration((performance.now() - started) / 1000);
        setLoading(false);
      }
    }
  }
  return (
    <div className="scientific-page">
      <div className="page-intro">
        <h1>Analizar una cita</h1>
        <p>
          Recupera tres fragmentos del artículo citado y clasifica la función de una cita en inglés.
        </p>
      </div>
      <nav className="workflow-progress" aria-label="Pasos del análisis">
        <ol>
          {['Contexto', 'Artículo', 'Clasificador', 'Resultados'].map((name, index) => (
            <li
              key={name}
              className={`${index === step ? 'step-active' : ''} ${index < completedSteps ? 'step-complete' : ''}`}
            >
              <button
                id={`workflow-step-${index}`}
                type="button"
                disabled={loading || (!completed && index > step)}
                aria-current={index === step ? 'step' : undefined}
                onClick={() => goToStep(index)}
              >
                <b aria-hidden="true">{index < completedSteps ? '✓' : index + 1}</b>
                <span>
                  {name}
                  <span className="sr-only">
                    {index === step
                      ? ': etapa actual'
                      : index < completedSteps
                        ? ': completada'
                        : ': pendiente'}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      </nav>
      <section className="workspace" aria-label="Análisis de cita" hidden={step === 3}>
        <form onSubmit={submitStep}>
          <fieldset
            className="analysis-step"
            id="citation-step"
            hidden={step !== 0}
            disabled={step !== 0}
          >
            <legend id="workflow-title-0" tabIndex={-1}>
              Contexto en inglés
            </legend>
            <label className="sr-only" htmlFor="citation-context">
              Contexto en inglés
            </label>
            <textarea
              id="citation-context"
              ref={input}
              lang="en"
              rows={6}
              value={context}
              placeholder="Previous research [Smith, 2020] introduced…"
              aria-describedby={`context-help context-state${errorField === 'citation-context' ? ' analysis-error' : ''}`}
              aria-invalid={errorField === 'citation-context' || undefined}
              onChange={(e) => {
                resetWorkflow();
                setContext(e.target.value);
              }}
            />
            <p id="context-help" className="field-help">
              Selecciona la referencia en el texto y pulsa «Marcar cita».
            </p>
            <div className="context-feedback" id="context-state" aria-live="polite">
              <span className={context.length > 4000 || markerCount > 1 ? 'invalid-text' : ''}>
                {context.length.toLocaleString('es')} / 4.000 caracteres
              </span>
              <span>
                {markerCount === 1
                  ? target
                    ? `Cita objetivo: ${target}`
                    : 'Una cita marcada'
                  : markerCount > 1
                    ? 'Hay varias marcas: deja solo una'
                    : 'Cita sin marcar'}
              </span>
            </div>
            <div className="context-actions">
              <button type="button" className="text-button" onClick={mark}>
                Marcar cita
              </button>
              <button type="button" className="text-button" onClick={example}>
                Usar ejemplo público
              </button>
              <button type="button" className="text-button" onClick={() => setExamplesOpen(true)}>
                Explorar ejemplos del dataset
              </button>
            </div>
            {usingExample && <p className="field-help">Ejemplo público sintético.</p>}
            {selectedExample && <p className="field-help">Ejemplo de ACL-200 · validación.</p>}
          </fieldset>
          <fieldset
            className="analysis-step"
            id="article-step"
            hidden={step !== 1}
            disabled={step !== 1}
          >
            <legend id="workflow-title-1" tabIndex={-1}>
              Artículo citado
            </legend>
            <div className="article-filter">
              <label htmlFor="article-filter">Filtrar artículos por título o ID</label>
              <input
                id="article-filter"
                type="search"
                value={articleQuery}
                placeholder="Por ejemplo: translation o W05-0821"
                onChange={(event) => setArticleQuery(event.target.value)}
                aria-describedby="article-filter-count"
              />
              <p id="article-filter-count" className="field-help" aria-live="polite">
                {filteredArticles.length} coincidencias en {catalog.articulos.length} artículos del
                catálogo.
                {articleQuery && article && !filteredArticles.includes(article)
                  ? ' Conservamos tu artículo seleccionado.'
                  : ''}
              </p>
            </div>
            <label htmlFor="cited-article">Artículo preparado por título e ID</label>
            <select
              id="cited-article"
              aria-invalid={errorField === 'cited-article' || undefined}
              aria-describedby={`article-help${errorField === 'cited-article' ? ' analysis-error' : ''}`}
              value={paperId}
              onChange={(e) => {
                invalidate();
                setPaperId(e.target.value);
                setUsingExample(false);
                setSelectedExample('');
              }}
            >
              <option value="">Selecciona la referencia citada</option>
              {articleOptions.map((item) => (
                <option key={item.paper_id} value={item.paper_id}>
                  {item.titulo} · {item.paper_id}
                </option>
              ))}
            </select>
            {article && (
              <p className="selected-article">
                <strong>{article.titulo}</strong> · {article.paper_id}
                <br />
                <a href={article.publicacion} target="_blank" rel="noreferrer">
                  Abrir publicación
                </a>
              </p>
            )}
            {article && (
              <div className="coverage-status" aria-live="polite">
                {coverageStatus === 'checking' && <p role="status">Consultando texto preparado…</p>}
                {coverageStatus === 'available' && (
                  <p role="status">Texto preparado: disponible.</p>
                )}
                {coverageStatus === 'missing' && (
                  <p role="status">
                    Este artículo no tiene texto preparado en el servicio. Conservamos tu contexto;
                    selecciona otro artículo.
                  </p>
                )}
                {coverageStatus === 'error' && (
                  <>
                    <p role="status">
                      No se pudo consultar la disponibilidad. Esto no significa que falte el texto
                      del artículo.
                    </p>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => {
                        setCoverage({ paperId, status: 'checking' });
                        setCoverageRetry((count) => count + 1);
                      }}
                    >
                      Reintentar disponibilidad
                    </button>
                  </>
                )}
              </div>
            )}
            <p className="field-help" id="article-help">
              Elige la referencia que ya conoces. Los fragmentos se recuperan únicamente dentro de
              ese artículo.
            </p>
          </fieldset>
          <fieldset
            className="analysis-step"
            id="classifier-step"
            hidden={step !== 2}
            disabled={step !== 2}
          >
            <legend id="workflow-title-2" tabIndex={-1}>
              Clasificador
            </legend>
            <label htmlFor="classifier">Familia y modelo</label>
            <select
              id="classifier"
              aria-describedby="classifier-help"
              value={variant}
              onChange={(e) => {
                invalidate();
                setVariant(e.target.value as 'M' | 'S' | 'commercial');
              }}
            >
              <optgroup label="Encoder SciBERT ajustado">
                <option value="M">Encoder SciBERT — M</option>
                <option value="S">Encoder SciBERT — S</option>
              </optgroup>
              {commercialAvailable && <option value="commercial">Comercial — GPT-6.1 Sol</option>}
            </select>
            {catalogStatus === 'checking' && (
              <p className="field-help" role="status">
                Consultando clasificadores disponibles…
              </p>
            )}
            {catalogStatus === 'error' && (
              <div className="catalog-notice">
                <p>No se pudo consultar el catálogo de clasificadores. Puedes usar M/S.</p>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => setCatalogRetry((count) => count + 1)}
                >
                  Reintentar catálogo
                </button>
              </div>
            )}
            <p className="field-help" id="classifier-help">
              {variant === 'commercial'
                ? 'SciBERT recupera los fragmentos. OpenAI recibe el contexto, el título y el resumen para clasificar la función.'
                : 'Usa el contexto de la cita y fragmentos del artículo. Se calculan M y S; verás la variante elegida.'}
            </p>
          </fieldset>
          {step === 2 && variant === 'commercial' && (
            <label className="field-help commercial-consent">
              <input
                id="commercial-consent"
                aria-invalid={errorField === 'commercial-consent' || undefined}
                aria-describedby={
                  errorField === 'commercial-consent' ? 'analysis-error' : undefined
                }
                type="checkbox"
                disabled={loading}
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              Acepto enviar el contexto de cita, título y resumen a OpenAI para este análisis.
            </label>
          )}
          {error && step !== 3 && (
            <p id="analysis-error" tabIndex={-1} role="alert" className="error-message">
              {error}
            </p>
          )}
          <div className="analysis-submit">
            {guidance && <p className="readiness-message">{guidance}</p>}
            <div className="step-actions">
              {step > 0 && (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={loading}
                  onClick={() => goToStep(step - 1)}
                >
                  Anterior
                </button>
              )}
              {step < 2 ? (
                <button
                  type="submit"
                  className="primary"
                  disabled={step === 0 ? !contextReady : !article || coverageStatus !== 'available'}
                >
                  {step === 0 ? 'Siguiente: artículo' : 'Siguiente: clasificador'}
                </button>
              ) : completed ? (
                <button type="button" className="primary" onClick={() => goToStep(3)}>
                  Ver resultados
                </button>
              ) : (
                <button
                  type="submit"
                  className="primary"
                  disabled={loading || !contextReady || !article || coverageStatus !== 'available'}
                >
                  {loading ? 'Analizando cita…' : 'Analizar cita'}
                </button>
              )}
            </div>
          </div>
          {loading && (
            <p className="analysis-loading" role="status">
              {phase === 'retrieving'
                ? 'Recuperando fragmentos y clasificando la cita…'
                : 'Esperando la función predicha de OpenAI. Puedes consultar el Top-3.'}
            </p>
          )}
        </form>
      </section>
      {step === 3 && result && (
        <section
          id="analysis-results"
          tabIndex={-1}
          className="analysis-output"
          aria-label="Resultado del análisis"
        >
          {error && (
            <p id="analysis-error" tabIndex={-1} role="alert" className="error-message">
              {error}
            </p>
          )}
          <div className="analysis-summary">
            <p className="result-kicker">
              {loading
                ? 'Resultado parcial'
                : error
                  ? 'Fragmentos disponibles · clasificación incompleta'
                  : 'Análisis completado'}
              {duration !== undefined && <span> · {duration.toFixed(1)} s en total</span>}
            </p>
            <p>
              <strong>{result.articulo.titulo}</strong> · {paperId} ·{' '}
              {variant === 'commercial'
                ? 'Comercial — GPT-6.1 Sol'
                : `Encoder SciBERT — ${variant}`}
            </p>
          </div>
          <div className="result-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={loading}
              onClick={() => goToStep(2)}
            >
              Volver al clasificador
            </button>
            <button
              type="button"
              className="text-button"
              disabled={loading}
              onClick={() => goToStep(0)}
            >
              Editar contexto
            </button>
          </div>
          <ScientificResults
            respuesta={result}
            variante={variant === 'commercial' ? undefined : variant}
            commercialSelected={variant === 'commercial'}
            commercial={commercialResult}
            commercialPending={loading && phase === 'classifying'}
            fuente={result.articulo.publicacion}
          />
          {result.articulo.fuente && (
            <p className="field-help">
              <a href={result.articulo.fuente} target="_blank" rel="noreferrer">
                Texto fuente del artículo
              </a>{' '}
              · {result.articulo.licencia}
            </p>
          )}
        </section>
      )}
      {examplesOpen && (
        <ExampleDialog
          examples={datasetExamples.ejemplos.map((item) => ({
            context_id: item.context_id,
            texto: item.contexto,
            titulo_correcto: item.titulo,
            cita_correcta: item.paper_id,
            detalle: `${item.paper_id} · Citado desde ${item.citing_id} · Validación`,
          }))}
          selected={selectedExample}
          searchable
          description="Citas de ACL-200 con artículo preparado. Elige una para cargar el contexto y la referencia."
          onSelect={selectDatasetExample}
          onClose={() => setExamplesOpen(false)}
        />
      )}
      <details id="ayuda" className="analysis-help">
        <summary>Cómo analizar una cita</summary>
        <p>
          Pega el contexto en inglés, selecciona la referencia y marca la cita. Confirma el artículo
          citado, elige el clasificador y pulsa «Analizar cita».
        </p>
        <p>
          Los fragmentos son candidatos relacionados; no prueban por sí solos la afirmación. Las
          puntuaciones del clasificador no son porcentajes de acierto.
        </p>
      </details>
    </div>
  );
}
