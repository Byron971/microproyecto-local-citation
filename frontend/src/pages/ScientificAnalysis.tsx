import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  ApiError,
  errorMessage,
  request,
  startAnalysisJob,
  followAnalysisJob,
  readAnalysisJob,
  cancelAnalysisJob,
  newIdempotencyKey,
  type AnalysisJob,
  type JobState,
} from '../api';
import { ScientificResults, type Respuesta } from '../components/ScientificResults';
import catalog from '../articleCatalog.json';
import fullCatalogUrl from '../fullArticleCatalog.json?url';
import datasetExamples from '../scientificExamples.json';
import { ExampleDialog } from '../components/ExampleDialog';
import {
  ArticlePicker,
  type PreparedArticle,
  type TruncationInfo,
  truncationNotice,
} from '../components/ArticlePicker';
import type { CommercialClassification } from '../components/CommercialResults';
import { detectCitations, markCitation, type CitationSpan } from '../citationDetection';

type Analysis = Respuesta & {
  articulo: {
    paper_id: string;
    titulo: string;
    publicacion: string;
    fuente?: string;
    licencia?: string;
    version_contenido?: string;
    truncamiento?: TruncationInfo;
  };
};
type Coverage = {
  paperId: string;
  status: 'checking' | 'available' | 'missing' | 'error';
  version?: string;
  truncation?: TruncationInfo;
};

type Variant = 'M' | 'S' | 'commercial';
// Seguimiento recuperable tras recargar: solo en esta pestaña (sessionStorage).
const STORAGE_KEY = 'citas.analisisMS';
type StoredJob = {
  trabajo_id: string;
  texto: string;
  span?: CitationSpan;
  paper_id: string;
  variante: Variant;
  version?: string;
};
function saveJob(job: StoredJob) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(job));
  } catch {
    /* Sin almacenamiento: el análisis sigue, pero no se recupera al recargar. */
  }
}
function loadJob(): StoredJob | undefined {
  try {
    const job = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
    if (
      job &&
      /^[a-f0-9]{32}$/.test(job.trabajo_id) &&
      typeof job.texto === 'string' &&
      typeof job.paper_id === 'string' &&
      ['M', 'S', 'commercial'].includes(job.variante)
    )
      return job;
  } catch {
    /* Entrada dañada: se ignora. */
  }
  clearJob();
  return undefined;
}
function clearJob() {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* Nada que borrar. */
  }
}
type Tracking = { id: string; estado: JobState; reintentando?: boolean };

export function ScientificAnalysis() {
  const [articles, setArticles] = useState<PreparedArticle[]>(catalog.articulos);
  const [articleCatalogVersion, setArticleCatalogVersion] = useState<string>();
  const [articleCatalogError, setArticleCatalogError] = useState(false);
  const [articleCatalogRetry, setArticleCatalogRetry] = useState(0);
  const [text, setText] = useState('');
  const [chosenSpan, setChosenSpan] = useState<CitationSpan>();
  const [paperId, setPaperId] = useState('');
  const [variant, setVariant] = useState<Variant>('M');
  const [commercialAvailable, setCommercialAvailable] = useState(false);
  const [catalogStatus, setCatalogStatus] = useState<'checking' | 'ready' | 'error'>('checking');
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [consent, setConsent] = useState(false);
  const [commercialResult, setCommercialResult] = useState<CommercialClassification>();
  const [coverage, setCoverage] = useState<Coverage>();
  const [coverageRetry, setCoverageRetry] = useState(0);
  const [selectedExample, setSelectedExample] = useState('');
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [result, setResult] = useState<Analysis>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorField, setErrorField] = useState('');
  const [articleReset, setArticleReset] = useState(0);
  const [searchingArticles, setSearchingArticles] = useState(false);
  const [phase, setPhase] = useState<'retrieving' | 'classifying'>('retrieving');
  const [tracking, setTracking] = useState<Tracking>();
  const [cancelling, setCancelling] = useState(false);
  const [cancelNotice, setCancelNotice] = useState('');
  const starting = useRef(false);
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
      .then(
        (full: {
          source_sha256: string;
          version_contenido: string;
          articulos: PreparedArticle[];
        }) => {
          if (
            !Array.isArray(full.articulos) ||
            !/^[a-f0-9]{64}$/.test(full.source_sha256) ||
            full.version_contenido !== catalog.version_contenido
          )
            throw new Error('Invalid catalog');
          if (!controller.signal.aborted) {
            setArticles(full.articulos);
            setArticleCatalogVersion(full.source_sha256);
            setArticleCatalogError(false);
          }
        },
      )
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
    request<{
      version_contenido: string;
      articulos: { paper_id: string; disponible: boolean; truncamiento?: TruncationInfo }[];
    }>('/api/analisis-cita-ms/disponibilidad', {
      method: 'POST',
      signal: controller.signal,
      body: JSON.stringify({ paper_ids: [paperId] }),
    })
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
          truncation: entry.truncamiento,
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

  function selectDatasetExample(id: string) {
    const item = datasetExamples.ejemplos.find((entry) => entry.context_id === id);
    if (!item) return;
    resetWorkflow();
    setText(item.contexto);
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
    setSelectedExample('');
  }

  function invalidate() {
    setCompleted(false);
    setCompletedSteps(Math.min(step, 2));
    active.current?.abort();
    clearJob();
    setTracking(undefined);
    setCancelNotice('');
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
  async function run(event?: FormEvent) {
    event?.preventDefault();
    if (loading || step < 2) return;
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
    if (starting.current) return; // Doble clic: un único POST.
    starting.current = true;
    active.current?.abort();
    setResult(undefined);
    setCommercialResult(undefined);
    setError('');
    setCancelNotice('');
    setTracking(undefined);
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setCompleted(false);
    setCompletedSteps(3);
    setStep(3);
    setErrorField('');
    setPhase('retrieving');
    setDuration(undefined);
    const started = performance.now();
    const options = { paperId, version: coverage?.version, variant, context, restored: false };
    let admitted = false;
    try {
      const job = await startAnalysisJob<Analysis>(
        context,
        paperId,
        newIdempotencyKey(),
        controller.signal,
      );
      admitted = true;
      if (controller.signal.aborted) return;
      saveJob({
        trabajo_id: job.trabajo_id,
        texto: text,
        span: chosenSpan,
        paper_id: paperId,
        variante: variant,
        version: coverage?.version,
      });
      await finish(job, controller, options);
    } catch (err) {
      // Un 404 de la admisión indica que el artículo ya no tiene texto preparado.
      if (!admitted && err instanceof ApiError && err.status === 404 && !controller.signal.aborted)
        setCoverage({ paperId, status: 'missing' });
      fail(err, controller);
    } finally {
      starting.current = false;
      if (!controller.signal.aborted) {
        setDuration((performance.now() - started) / 1000);
        setLoading(false);
      }
    }
  }
  function fail(err: unknown, controller: AbortController) {
    if (controller.signal.aborted) return;
    setErrorField('analysis-error');
    setError(errorMessage(err));
  }
  async function finish(
    job: AnalysisJob<Analysis>,
    controller: AbortController,
    options: {
      paperId: string;
      version?: string;
      variant: Variant;
      context: string;
      restored: boolean;
    },
  ) {
    const track = (next: AnalysisJob<Analysis>) =>
      setTracking({ id: next.trabajo_id, estado: next.estado, reintentando: next.reintentando });
    track(job);
    const final = await followAnalysisJob(job, controller.signal, track);
    if (controller.signal.aborted) return;
    if (final.estado !== 'completado')
      throw new ApiError(
        final.estado === 'cancelado'
          ? 'Cancelaste el análisis antes de que empezara. Tu contexto y la selección se conservan.'
          : (final.error?.mensaje ?? 'No se pudo completar el análisis científico.'),
        409,
      );
    const data = final.resultado!;
    if (
      data.articulo?.paper_id !== options.paperId ||
      (options.version !== undefined && data.articulo?.version_contenido !== options.version) ||
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
    if (options.variant === 'commercial') {
      if (options.restored) {
        // Nunca reenviar al proveedor comercial por una recarga: evita cobros duplicados.
        setErrorField('analysis-error');
        setError(
          'Recuperamos los fragmentos. La clasificación comercial no se repitió al recargar la página; vuelve al clasificador para solicitarla.',
        );
        return;
      }
      setPhase('classifying');
      const commercial = await request<CommercialClassification>('/api/comercial/clasificar', {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({
          contexto: options.context,
          paper_id: options.paperId,
          consentimiento: consent,
        }),
      });
      if (controller.signal.aborted) return;
      if (
        commercial.paper_id !== options.paperId ||
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
  }
  async function cancel() {
    if (!tracking || cancelling) return;
    setCancelling(true);
    setCancelNotice('');
    try {
      await cancelAnalysisJob(tracking.id);
      setCancelNotice('Cancelación registrada. Se confirmará en unos segundos.');
    } catch (err) {
      setCancelNotice(errorMessage(err));
    } finally {
      setCancelling(false);
    }
  }
  // Retomar un análisis de esta pestaña tras recargar: solo consulta, nunca otro POST.
  useEffect(() => {
    const stored = loadJob();
    if (!stored) return;
    setText(stored.texto);
    setChosenSpan(stored.span);
    setPaperId(stored.paper_id);
    setVariant(stored.variante);
    setCompletedSteps(3);
    setStep(3);
    setLoading(true);
    setPhase('retrieving');
    const controller = new AbortController();
    active.current = controller;
    readAnalysisJob<Analysis>(stored.trabajo_id, controller.signal)
      .then((job) =>
        finish(job, controller, {
          paperId: stored.paper_id,
          version: stored.version,
          variant: stored.variante,
          context: '',
          restored: true,
        }),
      )
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) clearJob();
        fail(err, controller);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // Solo al montar: retoma el trabajo guardado una vez.
  }, []);
  const queued = tracking?.estado === 'en_cola' && !tracking.reintentando;
  const loadingTitle =
    phase === 'classifying'
      ? 'Clasificando la función de la cita…'
      : tracking?.reintentando
        ? 'Reanudando el análisis…'
        : queued
          ? 'En cola'
          : tracking?.estado === 'procesando'
            ? 'Calculando los resultados…'
            : 'Enviando el análisis…';
  const loadingDetail =
    phase === 'classifying'
      ? 'Los tres fragmentos ya están disponibles. Esperando la clasificación de OpenAI.'
      : tracking?.reintentando
        ? 'El servicio se reinició durante el cálculo. Se volverá a calcular automáticamente una vez.'
        : queued
          ? 'Hay otro análisis en curso. El tuyo empezará cuando termine.'
          : tracking?.estado === 'procesando'
            ? 'Buscamos los tres fragmentos del artículo y calculamos la clasificación.'
            : 'Registrando la solicitud en el servicio científico.';
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
                <b>{index + 1}</b>
                <span>
                  {name}
                  {index < completedSteps && (
                    <span className="workflow-check" aria-hidden="true">
                      {' '}
                      ✓
                    </span>
                  )}
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
              Pega el párrafo que contiene la cita.
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
                No se pudo cargar el catálogo completo. Puedes usar el catálogo inicial.{' '}
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
              isActive={step === 1 && contextReady}
              selected={paperId}
              coverage={coverageStatus}
              truncation={coverage?.truncation}
              onBusyChange={setSearchingArticles}
              onSelect={(id) => {
                if (id === paperId) return;
                invalidate();
                setPaperId(id);
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
              {step === 0 && (
                <button
                  type="button"
                  className="secondary-button"
                  aria-haspopup="dialog"
                  onClick={() => setExamplesOpen(true)}
                >
                  Explorar ejemplos
                </button>
              )}
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
                  Ver resultados
                </button>
              )}
            </div>
          </div>
        </form>
      </section>
      {step === 3 && (
        <section
          id="analysis-results"
          tabIndex={-1}
          className="analysis-output"
          aria-label="Resultado del análisis"
        >
          <h2 id="workflow-title-3" tabIndex={-1}>
            Resultados
          </h2>
          {loading && (
            <>
              {/* Solo cambia el texto al cambiar de estado: el polling no genera anuncios. */}
              <div className="results-loading" role="status" aria-atomic="true">
                <span className="analysis-spinner" aria-hidden="true" />
                <div>
                  <h3>{loadingTitle}</h3>
                  <p>{loadingDetail}</p>
                  <p className="field-help">
                    Si recargas esta página, el seguimiento continúa; no hace falta reenviar el
                    análisis.
                  </p>
                </div>
              </div>
              {queued && (
                <div className="result-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={cancelling}
                    onClick={() => void cancel()}
                  >
                    {cancelling ? 'Cancelando…' : 'Cancelar análisis'}
                  </button>
                  <p className="field-help" aria-live="polite">
                    {cancelNotice || 'Solo puede cancelarse mientras espera en la cola.'}
                  </p>
                </div>
              )}
              {!queued && cancelNotice && (
                <p className="field-help" aria-live="polite">
                  {cancelNotice}
                </p>
              )}
            </>
          )}
          {error && (
            <p id="analysis-error" tabIndex={-1} role="alert" className="error-message">
              {error}
            </p>
          )}
          {!result && !loading && error && (
            <div className="result-actions">
              {coverageStatus === 'available' && (
                <button type="button" className="primary" onClick={() => void run()}>
                  Volver a intentar
                </button>
              )}
              <button
                type="button"
                className="secondary-button"
                onClick={() => goToStep(coverageStatus === 'available' ? 2 : 1)}
              >
                {coverageStatus === 'available' ? 'Volver al clasificador' : 'Revisar artículo'}
              </button>
              <p className="field-help">
                Tu contexto y la selección se conservan. El análisis solo se repite si pulsas
                «Volver a intentar».
              </p>
            </div>
          )}
          {result && (
            <>
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
              {result.articulo.truncamiento?.aplicado && (
                <p className="field-help">{truncationNotice(result.articulo.truncamiento)}</p>
              )}
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
                hideHeading
                respuesta={result}
                truncation={result.articulo.truncamiento}
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
            </>
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
            detalle: `${item.tema} · ${item.paper_id} · ACL-200 (validación)`,
          }))}
          selected={selectedExample}
          searchable
          description="Citas en inglés de distintas áreas de PLN. Elige una para cargar su contexto; confirma el artículo después."
          onSelect={selectDatasetExample}
          onClose={() => setExamplesOpen(false)}
        />
      )}
    </div>
  );
}
