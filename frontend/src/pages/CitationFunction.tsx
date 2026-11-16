import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError, errorMessage, type ClassificationResponse } from '../api';

export function CitationFunction() {
  const [context, setContext] = useState('');
  const [title, setTitle] = useState('');
  const [abstract, setAbstract] = useState('');
  const [encoder, setEncoder] = useState<'scibert' | 'specter'>('scibert');
  const [result, setResult] = useState<ClassificationResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const current = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => () => current.current?.abort(), []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if ((context.match(/TARGETCIT/g) ?? []).length !== 1
        || !title.trim() || !abstract.trim()) {
      setError('Escribe un contexto con un único TARGETCIT, título y abstract del artículo citado.');
      return;
    }
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    setLoading(true);
    setError('');
    setResult(undefined);
    try {
      const answer = await (encoder === 'scibert'
        ? api.classifyCitation(context.trim(), title.trim(), abstract.trim(), controller.signal)
        : api.classifyCitationSpecterA(context.trim(), title.trim(), abstract.trim(), controller.signal));
      if (controller.signal.aborted) return;
      if (answer.entrada !== 'A' || answer.encoder !== encoder
          || answer.training_labels !== 'Haiku'
          || answer.validacion !== 'provisional_no_gold_humano'
          || answer.puntuaciones_softmax.length !== 9) {
        throw new Error('La respuesta no corresponde al clasificador A4 provisional esperado.');
      }
      setResult(answer);
      requestAnimationFrame(() => heading.current?.focus());
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(err instanceof ApiError && err.status === 503
        ? 'El clasificador A4 no está instalado con un checkpoint verificado. '
          + 'La función de cita no se puede estimar en esta instalación.'
        : errorMessage(err));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">Experimental · Función retórica de la cita</span>
          <h1>Clasificar la función de una cita</h1>
          <p>Entrada A: contexto con TARGETCIT, título y resumen del artículo citado.</p>
        </div>
      </div>
      <p className="notice" role="note">
        Selecciona SciBERT-A o SPECTER-A, ambos requieren su checkpoint original
        SHA-verificado. Entrenamiento con etiquetas automáticas Haiku: resultados provisionales,
        no están validados sobre Test Gold humano.
      </p>
      <section className="workspace" aria-label="Clasificador de función de cita">
        <form onSubmit={submit}>
          <label htmlFor="function-encoder">Encoder de clasificación A</label>
          <select id="function-encoder" value={encoder} disabled={loading}
            onChange={(e) => { setEncoder(e.target.value as 'scibert' | 'specter'); setResult(undefined); }}>
            <option value="scibert">SciBERT-A (checkpoint requerido)</option>
            <option value="specter">SPECTER-A (checkpoint requerido)</option>
          </select>
          <label htmlFor="function-context">Contexto de cita (en inglés)</label>
          <textarea
            id="function-context" lang="en" rows={4} maxLength={4000}
            value={context} onChange={(e) => setContext(e.target.value)}
            placeholder="We compare earlier approaches TARGETCIT with our method."
          />
          <label htmlFor="function-title">Título real del artículo citado</label>
          <input
            id="function-title" lang="en" maxLength={600} value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <label htmlFor="function-abstract">Abstract real del artículo citado</label>
          <textarea
            id="function-abstract" lang="en" rows={6} maxLength={12000}
            value={abstract} onChange={(e) => setAbstract(e.target.value)}
          />
          <div className="form-actions">
            <button type="submit" className="primary" disabled={loading}>
              {loading ? 'Clasificando…' : 'Clasificar función de cita'}
            </button>
          </div>
          {error && <p className="error-message" role="alert">{error}</p>}
        </form>
      </section>
      {result && (
        <section className="results-section">
          <div className="section-heading">
            <h2 ref={heading} tabIndex={-1}>Función estimada: {result.clase}</h2>
            <span>{result.modelo} · Entrada A</span>
          </div>
          <p className="notice" role="status">
            Resultado provisional de un modelo entrenado con Haiku. No está certificado
            con etiquetas humanas ni constituye una certeza de la función.
          </p>
          <h3>Puntuaciones del clasificador</h3>
          <p className="field-help">
            Valores softmax sin calibración. No interpretarlos como probabilidades de acierto.
          </p>
          <ol className="fragment-list">
            {result.puntuaciones_softmax.map((p) => (
              <li key={p.categoria}>
                <div>
                  <span>{p.categoria}</span>
                  <span className="score">{p.score.toFixed(3)}</span>
                </div>
              </li>
            ))}
          </ol>
          <p className="field-help">
            Latencia de inferencia del modelo: {result.latencia_modelo_ms.toFixed(1)} ms,
            sin incluir red ni preparación. Modelo: {result.encoder} / {result.entrada}.
          </p>
        </section>
      )}
    </>
  );
}
