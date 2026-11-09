import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  api,
  ApiError,
  errorMessage,
  type Catalog,
  type ExamplesCatalog,
  type RecommendationResponse,
} from '../api';
import { readPreference, savePreference } from '../storage';
import { ExampleDialog } from '../components/ExampleDialog';
import { ModelSelect } from '../components/ModelSelect';
import { Results } from '../components/Results';
import { Icon } from '../components/Icon';

interface Snapshot {
  data: RecommendationResponse;
  model: string;
  label: string;
  description: string;
  key: string;
}
export function Recommend() {
  const [context, setContext] = useState('');
  const [count, setCount] = useState(() => {
    const n = Number(readPreference('citation-count', '10'));
    return [5, 10, 20].includes(n) ? n : 10;
  });
  const [model, setModel] = useState('');
  const [catalog, setCatalog] = useState<Catalog>();
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [example, setExample] = useState<{ id: string }>();
  const [examples, setExamples] = useState<ExamplesCatalog>();
  const exampleTrigger = useRef<HTMLButtonElement>(null);
  function closeExamples() {
    setExamplesOpen(false);
    exampleTrigger.current?.focus();
  }
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [exampleLoading, setExampleLoading] = useState(true);
  const [helpOpen, setHelpOpen] = useState(false);
  const [exampleError, setExampleError] = useState('');
  const [loading, setLoading] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Snapshot>();
  const active = useRef<AbortController | null>(null);
  const resultTitle = useRef<HTMLHeadingElement>(null);
  const catalogRetries = useRef(0);
  const selected = catalog?.modelos.find((m) => m.id === model);
  const currentKey = JSON.stringify([context.trim(), count, model]);
  useEffect(() => {
    const controller = new AbortController();
    api
      .models(controller.signal)
      .then((data) => {
        if (!data.modelos.length) throw new Error('Lista vacía');
        setCatalog(data);
        const saved = readPreference('citation-model', '');
        setModel(
          data.modelos.find((m) => m.id === saved && m.disponible)?.id ||
            data.modelos.find((m) => m.id === data.predeterminado && m.disponible)?.id ||
            data.modelos.find((m) => m.disponible)?.id ||
            '',
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) setCatalogFailed(true);
      });
    return () => {
      controller.abort();
      active.current?.abort();
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    api
      .examples(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setExamples(data);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setExampleError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setExampleLoading(false);
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!catalog || catalog.modelos.some((m) => m.disponible)) {
      catalogRetries.current = 0;
      return;
    }
    if (catalogRetries.current >= 12) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      catalogRetries.current++;
      api
        .models(controller.signal)
        .then((data) => {
          if (controller.signal.aborted) return;
          setCatalog(data);
          const available =
            data.modelos.find((m) => m.id === data.predeterminado && m.disponible) ||
            data.modelos.find((m) => m.disponible);
          if (available) setModel(available.id);
        })
        .catch(() => {
          if (!controller.signal.aborted) setCatalogFailed(true);
        });
    }, 5000);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [catalog]);
  useEffect(() => {
    savePreference('citation-count', String(count));
  }, [count]);
  useEffect(() => {
    if (model) savePreference('citation-model', model);
  }, [model]);
  useEffect(() => {
    if (attempted) {
      resultTitle.current?.focus({ preventScroll: true });
      resultTitle.current?.scrollIntoView({
        behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
          ? 'instant'
          : 'smooth',
        block: 'start',
      });
    }
  }, [attempted]);
  async function run(event?: FormEvent) {
    event?.preventDefault();
    if (!context.trim()) {
      setError('Escribe o pega un texto antes de pedir recomendaciones.');
      return;
    }
    if (catalog && !catalogFailed && !selected?.disponible) {
      setError('No hay un modelo disponible. Vuelve a intentarlo en unos segundos.');
      return;
    }
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setError('');
    setAttempted(true);
    setResult(undefined);
    const queryKey = currentKey;
    const chosen = selected;
    try {
      const response = await api.recommend(
        context.trim(),
        count,
        catalogFailed ? undefined : model || undefined,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setResult({
        data: response,
        key: queryKey,
        model: chosen?.nombre || response.modelo || 'Modelo predeterminado',
        label: chosen?.puntaje.etiqueta || 'Puntaje',
        description:
          chosen?.puntaje.descripcion ||
          'Puntaje devuelto por el modelo. Su significado no está disponible en este momento.',
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(errorMessage(err));
      if (err instanceof ApiError && [404, 409].includes(err.status)) {
        api
          .models(controller.signal)
          .then((data) => {
            setCatalog(data);
            setCatalogFailed(false);
          })
          .catch(() => setCatalogFailed(true));
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  function loadExample(id: string) {
    const data = examples?.ejemplos.find((item) => item.context_id === id);
    if (!data) return;
    setContext(data.texto);
    setExample({ id: data.context_id });
    closeExamples();
    setError('');
  }
  return (
    <div className="recommend-page">
      <div className="page-intro recommend-heading">
        <div>
          <h1>Encuentra referencias</h1>
          <p>Busca artículos relacionados con un fragmento de tu texto.</p>
        </div>
        <div
          className="heading-model"
          onBlur={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node)) setHelpOpen(false);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setHelpOpen(false);
          }}
        >
          <div className="model-label">
            <label id="model-label" htmlFor="model">
              Modelo
            </label>
            <button
              className="model-help-button"
              type="button"
              aria-label="Qué hace este modelo"
              aria-expanded={helpOpen}
              aria-controls="model-help-text"
              onClick={() => setHelpOpen((value) => !value)}
            >
              <span aria-hidden="true">i</span>
            </button>
          </div>
          <ModelSelect
            options={catalogFailed ? [] : catalog?.modelos || []}
            value={model}
            disabled={!catalog || catalogFailed}
            placeholder={
              catalogFailed
                ? 'Modelo predeterminado'
                : !catalog
                  ? 'Cargando modelos…'
                  : 'Selecciona un modelo'
            }
            onChange={(value) => {
              setModel(value);
              setHelpOpen(false);
            }}
          />
          {helpOpen && (
            <div id="model-help-text" className="model-help-text" role="note">
              {selected?.descripcion ||
                'El modelo busca y ordena artículos relacionados con tu texto. Puedes cambiarlo cuando haya otros disponibles.'}
            </div>
          )}
        </div>
      </div>
      <section className="workspace" aria-label="Recomendador de referencias">
        <form onSubmit={run}>
          {catalogFailed && (
            <p className="notice" role="status">
              No se pudo cargar la lista de modelos; se usará el predeterminado.
            </p>
          )}
          <label htmlFor="context">Contexto en inglés</label>
          <textarea
            id="context"
            lang="en"
            rows={6}
            spellCheck={false}
            value={context}
            aria-describedby={error ? 'query-error' : undefined}
            aria-invalid={!!error && !context.trim()}
            placeholder="Recent work on neural machine translation has shown that attention mechanisms…"
            onChange={(e) => {
              setContext(e.target.value);
              setExample(undefined);
            }}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                if (!loading) void run();
              }
            }}
          />
          {example && (
            <p className="example-source">
              Ejemplo real de ACL-200{examples?.particion === 'val' ? ' (validación)' : ''}.
              TARGETCIT marca la cita original.
            </p>
          )}
          <div className="form-actions">
            <button className="primary" disabled={loading} type="submit">
              <Icon name="search" size={20} />
              {loading ? 'Buscando…' : 'Recomendar'}
            </button>
            <div className="count-control">
              <label htmlFor="count">Resultados</label>
              <select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
                {[5, 10, 20].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="text-button example-picker"
              ref={exampleTrigger}
              disabled={exampleLoading || !examples?.ejemplos.length}
              onClick={() => setExamplesOpen(true)}
            >
              {exampleLoading
                ? 'Cargando ejemplos…'
                : !examples?.ejemplos.length
                  ? 'No hay ejemplos disponibles'
                  : 'Usar un ejemplo'}
            </button>
          </div>
          {exampleError && (
            <p className="error-message" role="alert">
              {exampleError}
            </p>
          )}
          {error && (
            <div id="query-error" className="error-message" role="alert">
              {error}
              {attempted && (
                <button type="button" className="text-button" onClick={() => void run()}>
                  Reintentar
                </button>
              )}
            </div>
          )}
        </form>
      </section>
      {examplesOpen && examples && (
        <ExampleDialog
          examples={examples.ejemplos}
          selected={example?.id}
          onSelect={loadExample}
          onClose={closeExamples}
        />
      )}
      {attempted && (
        <section className="results-section" aria-busy={loading}>
          <div className="section-heading">
            <div>
              <h2 ref={resultTitle} tabIndex={-1}>
                Referencias recomendadas{' '}
                {result && <span className="result-count">{result.data.total}</span>}
              </h2>
            </div>
            {result && <span className="result-model">{result.model}</span>}
          </div>
          <p className="sr-only" role="status">
            {loading
              ? 'Buscando referencias'
              : result
                ? `${result.data.total} referencias encontradas`
                : 'La consulta no se completó'}
          </p>
          {loading && (
            <div className="skeleton-list" aria-label="Cargando recomendaciones">
              {Array.from({ length: 5 }, (_, i) => (
                <div className="skeleton" key={i} />
              ))}
            </div>
          )}
          {result && (
            <>
              {result.key !== currentKey && (
                <p className="notice">
                  Resultados de la consulta anterior. Pulsa Recomendar para actualizar.
                </p>
              )}
              <p className="score-explanation">{result.description}</p>
              <Results
                key={result.key}
                rows={result.data.recomendaciones}
                label={result.label}
                scoreDescription={result.description}
              />
            </>
          )}
        </section>
      )}
      {result && <p className="method-note">Revisa el artículo antes de citarlo.</p>}
    </div>
  );
}
