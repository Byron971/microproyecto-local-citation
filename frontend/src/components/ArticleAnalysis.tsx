import { useEffect, useRef, useState } from 'react';
import { errorMessage, request } from '../api';
import { ScientificResults, type Respuesta } from './ScientificResults';

type ArticleResponse = Respuesta & {
  articulo: {
    paper_id: string;
    titulo: string;
    fuente: string;
    publicacion: string;
    sha256_ocl: string;
    version_contenido: string;
    total_fragmentos: number;
    licencia: string;
  };
};

export function ArticleAnalysis({ paperId, context }: { paperId: string; context: string }) {
  const [text, setText] = useState(context);
  const [result, setResult] = useState<ArticleResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  function change(value: string) {
    active.current?.abort();
    setLoading(false);
    setText(value);
    setResult(undefined);
    setError('');
  }
  function mark() {
    const el = input.current;
    if (!el) return;
    // Remove the previous marker while preserving the user's current selection offsets.
    const before = text.slice(0, el.selectionStart).replaceAll('TARGETCIT', '');
    const after = text.slice(el.selectionEnd).replaceAll('TARGETCIT', '');
    change(`${before} TARGETCIT ${after}`);
    el.focus();
  }
  async function run() {
    if (text.split('TARGETCIT').length !== 2 || text.length > 4000) {
      setError('Marca una posición de cita en un contexto de hasta 4000 caracteres.');
      return;
    }
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setResult(undefined);
    setError('');
    try {
      const data = await request<ArticleResponse>('/api/analisis-cita-ms/articulo', {
        method: 'POST',
        body: JSON.stringify({ paper_id: paperId, contexto: text }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (
        data.articulo.paper_id !== paperId ||
        data.top3?.length !== 3 ||
        data.clasificadores?.M.probabilidades.length !== 9 ||
        data.clasificadores?.S.probabilidades.length !== 9
      ) {
        throw new Error('La respuesta del análisis no corresponde al artículo o está incompleta.');
      }
      setResult(data);
    } catch (err) {
      if (!controller.signal.aborted) setError(errorMessage(err));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return (
    <section className="article-analysis" aria-label={`Análisis de ${paperId}`}>
      <h3>Analizar la cita · {paperId}</h3>
      <p>
        Haz clic donde irá la cita en el contexto y pulsa «Marcar posición de cita». También puedes
        seleccionar una cita existente para reemplazarla. La marca TARGETCIT identifica esa
        posición.
      </p>
      <label htmlFor={`citation-context-${paperId}`}>Contexto de la cita en inglés</label>
      <textarea
        ref={input}
        id={`citation-context-${paperId}`}
        lang="en"
        rows={4}
        maxLength={4000}
        value={text}
        onChange={(e) => change(e.target.value)}
      />
      <div className="form-actions">
        <button type="button" onClick={mark}>
          Marcar posición de cita
        </button>
        <button
          type="button"
          className="primary"
          disabled={loading || text.split('TARGETCIT').length !== 2}
          onClick={() => void run()}
        >
          {loading ? 'Analizando fragmentos y funciones…' : 'Analizar este artículo'}
        </button>
      </div>
      {loading && (
        <p role="status">
          SciBERT selecciona los tres fragmentos y M/S estiman la función de la cita.
        </p>
      )}
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {result && (
        <>
          <p>
            Se analizaron {result.articulo.total_fragmentos} fragmentos de este artículo.{' '}
            <a href={result.articulo.publicacion} target="_blank" rel="noreferrer">
              Abrir publicación
            </a>{' '}
            ·{' '}
            <a href={result.articulo.fuente} target="_blank" rel="noreferrer">
              Fuente ACL OCL
            </a>{' '}
            · {result.articulo.licencia}
          </p>
          <p className="field-help">
            M y S estiman funciones retóricas. Sus valores softmax no son porcentajes de acierto ni
            certifican que el artículo respalde la afirmación.
          </p>
          {result.clasificadores.M.clase !== result.clasificadores.S.clase && (
            <p className="notice">
              Los modelos discrepan: M estima {result.clasificadores.M.clase} y S estima{' '}
              {result.clasificadores.S.clase}.
            </p>
          )}
          <ScientificResults respuesta={result} />
        </>
      )}
    </section>
  );
}
