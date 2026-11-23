import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, errorMessage, request } from '../api';
import { ScientificResults, type Respuesta } from '../components/ScientificResults';
import catalog from '../articleCatalog.json';
import fullCatalogUrl from '../fullArticleCatalog.json?url';
import datasetExamples from '../scientificExamples.json';
import { ExampleDialog } from '../components/ExampleDialog';
import { ArticlePicker, type PreparedArticle } from '../components/ArticlePicker';
import type { CommercialClassification } from '../components/CommercialResults';
import { detectCitations, markCitation, type CitationSpan } from '../citationDetection';

export const PUBLIC_EXAMPLE = {
  paperId: 'W05-0821',
  context:
    'We use the language modeling approach described in [1] to improve a statistical machine translation system.',
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
  const [articles, setArticles] = useState<PreparedArticle[]>(catalog.articulos);
  const [articleCatalogVersion, setArticleCatalogVersion] = useState<string>();
  const [articleCatalogError, setArticleCatalogError] = useState(false);
  const [articleCatalogRetry, setArticleCatalogRetry] = useState(0);
  const [text, setText] = useState('');
  const [chosenSpan, setChosenSpan] = useState<CitationSpan>();
  const [paperId, setPaperId] = useState('');
  const [variant, setVariant] = useState<'M' | 'S' | 'commercial'>('M');
  const [commercialAvailable, setCommercialAvailable] = useState(false);
  const [catalogStatus, setCatalogStatus] = useState<'checking' | 'ready' | 'error'>('checking');
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [consent, setConsent] = useState(false);
  const [commercialResult, setCommercialResult] = useState<CommercialClassification>();
  const [coverage, setCoverage] = useState<Coverage>();
  const [coverageRetry, setCoverageRetry] = useState(0);
  const [usingExample, setUsingExample] = useState(false);
  const [selectedExample, setSelectedExample] = useState('');
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [result, setResult] = useState<Analysis>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorField, setErrorField] = useState('');
  const [articleReset, setArticleReset] = useState(0);
  const [searchingArticles, setSearchingArticles] = useState(false);
  const [phase, setPhase] = useState<'retrieving' | 'classifying'>('retrieving');
  const [duration, setDuration] = useState<number>();
  const [step, setStep] = useState(0);
  const [completed, setCompleted] = useState(false);
  const [completedSteps, setCompletedSteps] = useState(0);
  const input = useRef<HTMLTextAreaElement>(null);
  const active = useRef<AbortController | null>(null);
  const article = articles.find((item) => item.paper_id === paperId);
  useEffect(() => {
    if (step !== 1 || articleCatalogVersion) return;
    const controller = new AbortController();
    fetch(fullCatalogUrl, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Catalog unavailable');
        return response.json();
      })
      .then((full: { source_sha256: string; articulos: PreparedArticle[] }) => {
        if (!Array.isArray(full.articulos) || !/^[a-f0-9]{64}$/.test(full.source_sha256))
          throw new Error('Invalid catalog');
        if (!controller.signal.aborted) {
          setArticles(full.articulos);
          setArticleCatalogVersion(full.source_sha256);
          setArticleCatalogError(false);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setArticleCatalogError(true);
      });
    return () => controller.abort();
  }, [step, articleCatalogRetry, articleCatalogVersion]);
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

  const markerCount = text.split('TARGETCIT').length - 1;
  const candidates = markerCount === 0 ? detectCitations(text) : [];
  const options =
    chosenSpan && !candidates.some((c) => c.start === chosenSpan.start && c.end === chosenSpan.end)
      ? [...candidates, chosenSpan].sort((a, b) => a.start - b.start)
      : candidates;
  const targetSpan =
    markerCount === 0
      ? (chosenSpan ?? (candidates.length === 1 ? candidates[0] : undefined))
      : undefined;
  const context = targetSpan ? markCitation(text, targetSpan) : text;
  const contextReady =
    context.split('TARGETCIT').length === 2 &&
    context.length <= 4000 &&
    context.replace('TARGETCIT', '').trim().length > 0;
  const guidance =
    step === 2 && coverageStatus !== 'available'
      ? 'Vuelve al artículo citado para comprobar su disponibilidad.'
      : '';
  function goToStep(next: number) {
    if (
      loading ||
      searchingArticles ||
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
    setText(PUBLIC_EXAMPLE.context);
    setPaperId(PUBLIC_EXAMPLE.paperId);
    setUsingExample(true);
    setSelectedExample('');
    setCoverageRetry((count) => count + 1);
  }

  function selectDatasetExample(id: string) {
    const item = datasetExamples.ejemplos.find((entry) => entry.context_id === id);
    if (!item) return;
    resetWorkflow();
    setText(item.contexto);
    setPaperId(item.paper_id);
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
    setArticleReset((count) => count + 1);
    setSearchingArticles(false);
    setVariant('M');
    setChosenSpan(undefined);
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
  function chooseCitation(span: CitationSpan) {
    if (targetSpan?.start === span.start && targetSpan.end === span.end) return;
    resetWorkflow();
    setChosenSpan(span);
  }
  function applySelection() {
    const field = input.current;
    if (!field || field.selectionStart === field.selectionEnd) {
      reportError(
        'Selecciona la referencia dentro del texto y pulsa «Usar selección».',
        'citation-context',
      );
      return;
    }
    const start = field.selectionStart;
    const end = field.selectionEnd;
    const label = text.slice(start, end);
    if (!label.trim()) {
      reportError('La selección está vacía. Selecciona la referencia.', 'citation-context');
      return;
    }
    if (text.length - label.length + 'TARGETCIT'.length > 4000) {
      reportError('El contexto debe tener como máximo 4000 caracteres.', 'citation-context');
      return;
    }
    resetWorkflow();
    setChosenSpan({ start, end, label });
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
      reportError('Selecciona el artículo citado por su título e ID.', 'article-filter');
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
                disabled={loading || searchingArticles || (!completed && index > step)}
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
              value={text}
              placeholder="Previous research [Smith, 2020] introduced…"
              aria-describedby={`context-help context-state${errorField === 'citation-context' ? ' analysis-error' : ''}`}
              aria-invalid={errorField === 'citation-context' || undefined}
              onChange={(e) => {
                resetWorkflow();
                setText(e.target.value);
              }}
            />
            <p id="context-help" className="field-help">
              Incluye la referencia que quieres analizar, por ejemplo [1] o (Smith, 2020).
            </p>
            <div className="context-feedback" id="context-state" aria-live="polite">
              <span className={context.length > 4000 || markerCount > 1 ? 'invalid-text' : ''}>
                {context.length.toLocaleString('es')} / 4.000 caracteres
              </span>
              {markerCount > 1 && (
                <span className="invalid-text">Hay varias marcas: deja solo una</span>
              )}
              {markerCount === 1 && <span>Cita marcada en el texto como TARGETCIT</span>}
              {markerCount === 0 && options.length > 1 && !targetSpan && (
                <span>Elige la cita que quieres analizar</span>
              )}
              {targetSpan && <span className="sr-only">Cita a analizar: {targetSpan.label}</span>}
            </div>
            {markerCount === 0 && text.trim() && (
              <fieldset className="citation-choice">
                <legend>Cita a analizar</legend>
                {options.length > 0 && (
                  <div className="citation-options">
                    {options.map((option, index) => {
                      const repeated = options
                        .slice(0, index)
                        .filter((other) => other.label === option.label).length;
                      return (
                        <label key={`${option.start}-${option.end}`} className="citation-option">
                          <input
                            type="radio"
                            name="target-citation"
                            checked={
                              targetSpan?.start === option.start && targetSpan.end === option.end
                            }
                            onChange={() => chooseCitation(option)}
                          />
                          <span>
                            {option.label}
                            {repeated > 0 && (
                              <span className="citation-repeat"> · aparición {repeated + 1}</span>
                            )}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
                <p className="field-help citation-manual">
                  {options.length > 0
                    ? '¿No aparece? Selecciónala en el texto y pulsa'
                    : 'No se detectó ninguna referencia. Selecciónala en el texto y pulsa'}{' '}
                  <button type="button" className="text-button" onClick={applySelection}>
                    Usar selección
                  </button>
                </p>
              </fieldset>
            )}
            <div className="context-actions">
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
            {!articleCatalogVersion && !articleCatalogError && (
              <p role="status" className="field-help">
                Cargando catálogo completo…
              </p>
            )}
            {articleCatalogError && (
              <p role="alert" className="error-message">
                No se pudo cargar el catálogo completo. Puedes usar los artículos preparados.{' '}
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    setArticleCatalogError(false);
                    setArticleCatalogRetry((n) => n + 1);
                  }}
                >
                  Reintentar catálogo
                </button>
              </p>
            )}
            <ArticlePicker
              key={articleReset}
              articles={articles}
              version={catalog.version_contenido}
              catalogVersion={articleCatalogVersion}
              context={context}
              selected={paperId}
              coverage={coverageStatus}
              onBusyChange={setSearchingArticles}
              onSelect={(id) => {
                if (id === paperId) return;
                invalidate();
                setPaperId(id);
                setUsingExample(false);
                setSelectedExample('');
              }}
              onRetry={() => {
                setCoverage({ paperId, status: 'checking' });
                setCoverageRetry((count) => count + 1);
              }}
            />
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
                  disabled={loading || searchingArticles}
                  onClick={() => goToStep(step - 1)}
                >
                  Anterior
                </button>
              )}
              {step < 2 ? (
                <button
                  type="submit"
                  className="primary"
                  disabled={
                    searchingArticles ||
                    (step === 0 ? !contextReady : !article || coverageStatus !== 'available')
                  }
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
          Pega el contexto en inglés y elige la cita que quieres analizar. Confirma el artículo
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
