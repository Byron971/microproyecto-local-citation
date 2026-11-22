import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, errorMessage, request } from '../api';
import { ScientificResults, type Respuesta } from '../components/ScientificResults';
import catalog from '../articleCatalog.json';
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
  const [consent, setConsent] = useState(false);
  const [commercialResult, setCommercialResult] = useState<CommercialClassification>();
  const [target, setTarget] = useState('');
  const [coverage, setCoverage] = useState<Coverage>();
  const [coverageRetry, setCoverageRetry] = useState(0);
  const [usingExample, setUsingExample] = useState(false);
  const [result, setResult] = useState<Analysis>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  const active = useRef<AbortController | null>(null);
  const article = catalog.articulos.find((item) => item.paper_id === paperId);
  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    request<{ clasificadores: { id: string }[] }>('/api/clasificadores', {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted)
          setCommercialAvailable(data.clasificadores?.some((m) => m.id === 'commercial') === true);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);
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

  function example() {
    invalidate();
    setContext(PUBLIC_EXAMPLE.context);
    setTarget(PUBLIC_EXAMPLE.target);
    setPaperId(PUBLIC_EXAMPLE.paperId);
    setUsingExample(true);
    setCoverageRetry((count) => count + 1);
  }

  function invalidate() {
    active.current?.abort();
    setLoading(false);
    setResult(undefined);
    setCommercialResult(undefined);
    setConsent(false);
    setError('');
  }
  function mark() {
    const field = input.current;
    if (!field || field.selectionStart === field.selectionEnd) {
      setError('Selecciona la referencia dentro del contexto y pulsa «Marcar cita».');
      return;
    }
    const selected = context.slice(field.selectionStart, field.selectionEnd);
    if (selected.includes('TARGETCIT')) {
      setError('Selecciona la referencia original, no la marca TARGETCIT.');
      return;
    }
    const before = context.slice(0, field.selectionStart).replaceAll('TARGETCIT', target);
    const after = context.slice(field.selectionEnd).replaceAll('TARGETCIT', target);
    const marked = `${before}TARGETCIT${after}`;
    if (marked.length > 4000) {
      setError('El contexto marcado debe tener como máximo 4000 caracteres.');
      return;
    }
    invalidate();
    setTarget(selected);
    setContext(marked);
    field.focus();
  }
  async function run(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    if (!context.trim() || context.replaceAll('TARGETCIT', '').trim() === '') {
      setError('Escribe un contexto académico en inglés.');
      return;
    }
    if (context.split('TARGETCIT').length !== 2 || context.length > 4000) {
      setError('Marca una sola cita en un contexto de hasta 4000 caracteres.');
      return;
    }
    if (!article) {
      setError('Selecciona el artículo citado por su título e ID.');
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
      setError('Confirma el envío del texto a OpenAI antes de analizar.');
      return;
    }
    active.current?.abort();
    setResult(undefined);
    setCommercialResult(undefined);
    setError('');
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
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
      if (variant === 'commercial') {
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
    } catch (err) {
      if (!controller.signal.aborted) {
        if (err instanceof ApiError && err.status === 404)
          setCoverage({ paperId, status: 'missing' });
        setError(errorMessage(err));
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return (
    <div className="scientific-page">
      <div className="page-intro">
        <h1>Analizar una cita</h1>
        <p>Identifica fragmentos relacionados del artículo citado y la función de tu referencia.</p>
      </div>
      <section className="workspace" aria-label="Análisis de cita">
        <form onSubmit={run}>
          <fieldset className="analysis-step">
            <legend>1. Contexto de la cita</legend>
            <label htmlFor="citation-context">Contexto en inglés</label>
            <textarea
              id="citation-context"
              ref={input}
              lang="en"
              rows={6}
              value={context}
              aria-describedby="context-help"
              onChange={(e) => {
                invalidate();
                setContext(e.target.value);
                setUsingExample(false);
                if (!e.target.value.includes('TARGETCIT')) setTarget('');
              }}
            />
            <p id="context-help" className="field-help">
              Selecciona la referencia en el texto y pulsa «Marcar cita». Máximo 4000 caracteres.
            </p>
            <div className="context-actions">
              <button type="button" className="text-button" onClick={mark}>
                Marcar cita
              </button>
              <button type="button" className="text-button" onClick={example}>
                Usar ejemplo público
              </button>
            </div>
            {usingExample && (
              <p className="field-help">
                Contexto de demostración redactado para esta aplicación sobre una publicación
                pública. No procede de TRAIN ni Gold.
              </p>
            )}
            {context.includes('TARGETCIT') && (
              <p className="field-help">
                Cita objetivo: {target || 'posición marcada con TARGETCIT'}
              </p>
            )}
          </fieldset>
          <fieldset className="analysis-step">
            <legend>2. Artículo citado</legend>
            <label htmlFor="cited-article">Artículo preparado por título e ID</label>
            <select
              id="cited-article"
              value={paperId}
              onChange={(e) => {
                invalidate();
                setPaperId(e.target.value);
                setUsingExample(false);
              }}
            >
              <option value="">Selecciona la referencia citada</option>
              {catalog.articulos.map((item) => (
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
            <p className="field-help">
              Elige la referencia que ya conoces. Los fragmentos se recuperan únicamente dentro de
              ese artículo.
            </p>
          </fieldset>
          <fieldset className="analysis-step">
            <legend>3. Clasificador</legend>
            <label htmlFor="classifier">Familia y modelo</label>
            <select
              id="classifier"
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
            <p className="field-help">
              {variant === 'commercial'
                ? 'SciBERT recupera los fragmentos. OpenAI clasifica la función usando contexto, título y resumen.'
                : 'Usa el contexto y la entrada AB con fragmentos del artículo. El servicio calcula M y S; se muestra la variante elegida.'}
            </p>
          </fieldset>
          {variant === 'commercial' && (
            <label className="field-help commercial-consent">
              <input
                type="checkbox"
                disabled={loading}
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              Acepto enviar el contexto de cita, título y resumen a OpenAI para este análisis.
            </label>
          )}
          {error && (
            <p role="alert" className="error-message">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="primary"
            disabled={loading || (!!paperId && coverageStatus !== 'available')}
          >
            {loading ? 'Analizando cita…' : 'Analizar cita'}
          </button>
          {loading && <p role="status">Recuperando fragmentos y clasificando la cita…</p>}
        </form>
      </section>
      {result && (
        <section aria-label="Resultado del análisis">
          <p>
            <strong>{result.articulo.titulo}</strong> · {paperId} ·{' '}
            {variant === 'commercial' ? 'Comercial — GPT-6.1 Sol' : `Encoder SciBERT — ${variant}`}
          </p>
          <p>Cita objetivo: {target || 'posición marcada con TARGETCIT'}</p>
          <ScientificResults
            respuesta={result}
            variante={variant === 'commercial' ? undefined : variant}
            commercialSelected={variant === 'commercial'}
            commercial={commercialResult}
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
