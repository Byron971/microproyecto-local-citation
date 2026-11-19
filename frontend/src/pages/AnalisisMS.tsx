import { useEffect, useRef, useState, type FormEvent } from 'react';
import { errorMessage, request } from '../api';

type Candidato = { chunk_id: string; texto: string; seccion: string };
type Puntuacion = { clase: string; probabilidad: number };
type Clasificador = {
  clase: string;
  indice: number;
  probabilidad: number;
  ajuste_ph: boolean;
  probabilidades: Puntuacion[];
};
type Respuesta = {
  modelo_recuperacion: string;
  revision_scibert: string;
  dispositivo: string;
  tokens_ab: number;
  top3: (Candidato & { posicion: number; similitud_coseno: number; perfil: string })[];
  clasificadores: { M: Clasificador; S: Clasificador };
  aviso: string;
};

const DEMO = {
  contexto: 'Previous studies TARGETCIT introduced a neural approach for scientific document classification. We compare our architecture against this earlier approach.',
  titulo: 'Neural Methods for Scientific Text Classification',
  abstract: 'This study investigates neural representations for classification of scientific documents and reports empirical results across several corpora.',
  candidatos: [
    { chunk_id: 'p00001', seccion: 'Methods', texto: 'We train a neural encoder with a classification objective over labeled scientific documents.' },
    { chunk_id: 'p00002', seccion: 'Results', texto: 'The classifier improves macro F1 against a lexical baseline on the validation split.' },
    { chunk_id: 'p00003', seccion: 'Conclusion', texto: 'Our experiments suggest that contextual embeddings can support scientific document classification.' },
    { chunk_id: 'p00004', seccion: 'Related Work', texto: 'Earlier methods use lexical features and term frequency for classification of scholarly articles.' },
  ],
};

const percent = (x: number) => `${(x * 100).toFixed(2)} %`;

export function AnalisisMS() {
  const [contexto, setContexto] = useState('');
  const [titulo, setTitulo] = useState('');
  const [abstract, setAbstract] = useState('');
  const [candidatos, setCandidatos] = useState<Candidato[]>([
    { chunk_id: 'p00001', seccion: '', texto: '' },
    { chunk_id: 'p00002', seccion: '', texto: '' },
    { chunk_id: 'p00003', seccion: '', texto: '' },
  ]);
  const [respuesta, setRespuesta] = useState<Respuesta | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  function ejemplo() {
    controller.current?.abort();
    setContexto(DEMO.contexto);
    setTitulo(DEMO.titulo);
    setAbstract(DEMO.abstract);
    setCandidatos(DEMO.candidatos.map((c) => ({ ...c })));
    setRespuesta(null);
    setError('');
  }
  function actualizar(i: number, campo: keyof Candidato, valor: string) {
    setCandidatos((prev) => prev.map((c, j) => j === i ? { ...c, [campo]: valor } : c));
  }
  async function ejecutar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (contexto.split('TARGETCIT').length !== 2 || !titulo.trim() || !abstract.trim()) {
      setError('Se requiere un único TARGETCIT, título y abstract.');
      return;
    }
    if (candidatos.length < 3 || candidatos.some((c) => !c.texto.trim() || !c.chunk_id.trim())
      || new Set(candidatos.map((c) => c.chunk_id.trim())).size !== candidatos.length) {
      setError('Incluye al menos tres fragmentos con texto e identificadores únicos.');
      return;
    }
    controller.current?.abort();
    const actual = new AbortController();
    controller.current = actual;
    setCargando(true);
    setError('');
    setRespuesta(null);
    try {
      const resultado = await request<Respuesta>('/api/analisis-cita-ms', {
        method: 'POST',
        body: JSON.stringify({ contexto: contexto.trim(), titulo: titulo.trim(), abstract: abstract.trim(), candidatos }),
        signal: actual.signal,
      });
      if (!actual.signal.aborted) {
        if (!Array.isArray(resultado.top3) || resultado.top3.length !== 3 ||
          resultado.clasificadores.M.probabilidades.length !== 9 || resultado.clasificadores.S.probabilidades.length !== 9) {
          throw new Error('La respuesta no tiene tres fragmentos y nueve categorías por modelo.');
        }
        setRespuesta(resultado);
      }
    } catch (err) {
      if (!actual.signal.aborted) setError(err instanceof Error && err.message.startsWith('La respuesta') ? err.message : errorMessage(err));
    } finally {
      if (!actual.signal.aborted) setCargando(false);
    }
  }

  return <>
    <div className="page-intro"><div>
      <span className="eyebrow">Demostración científica · SciBERT + M/S</span>
      <h1>Recuperación y función de la cita</h1>
      <p>Recupera tres fragmentos del artículo citado y compara nueve funciones retóricas con los modelos M y S.</p>
    </div></div>
    <p className="notice" role="note">Prototipo experimental. Los fragmentos se suministran manualmente y deben pertenecer al mismo artículo citado. Los valores softmax no son probabilidades calibradas de acierto; la relevancia Top-3 y la precisión científica no están certificadas aquí.</p>
    <section className="workspace" aria-label="Análisis científico M/S">
      <form onSubmit={ejecutar}>
        <div className="form-actions">
          <button type="button" onClick={ejemplo} disabled={cargando}>Cargar ejemplo ilustrativo</button>
        </div>
        <label htmlFor="ms-contexto">Contexto académico en inglés (TARGETCIT una vez)</label>
        <textarea id="ms-contexto" lang="en" rows={4} maxLength={4000} required value={contexto} onChange={(e) => setContexto(e.target.value)} placeholder="Earlier work TARGETCIT showed..." />
        <label htmlFor="ms-titulo">Título del artículo citado</label>
        <input id="ms-titulo" lang="en" maxLength={600} required value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        <label htmlFor="ms-abstract">Abstract del artículo citado</label>
        <textarea id="ms-abstract" lang="en" rows={4} maxLength={12000} required value={abstract} onChange={(e) => setAbstract(e.target.value)} />
        <h2>Fragmentos candidatos</h2>
        <p className="field-help">Introduce al menos tres fragmentos del mismo artículo. SciBERT seleccionará automáticamente los Top-3.</p>
        {candidatos.map((c, i) => <div key={i} style={{ border: '1px solid #d6dded', borderRadius: '12px', padding: '1rem', marginBottom: '1rem' }}>
          <h3>Fragmento {i + 1}</h3>
          <label htmlFor={`ms-id-${i}`}>Identificador</label>
          <input id={`ms-id-${i}`} required maxLength={120} value={c.chunk_id} onChange={(e) => actualizar(i, 'chunk_id', e.target.value)} />
          <label htmlFor={`ms-seccion-${i}`}>Sección</label>
          <input id={`ms-seccion-${i}`} maxLength={200} value={c.seccion} onChange={(e) => actualizar(i, 'seccion', e.target.value)} />
          <label htmlFor={`ms-texto-${i}`}>Texto del fragmento</label>
          <textarea id={`ms-texto-${i}`} lang="en" required maxLength={5000} rows={3} value={c.texto} onChange={(e) => actualizar(i, 'texto', e.target.value)} />
        </div>)}
        <div className="form-actions">
          <button type="button" disabled={cargando || candidatos.length >= 100} onClick={() => setCandidatos((p) => [...p, { chunk_id: `p${String(p.length + 1).padStart(5,'0')}`, seccion: '', texto: '' }])}>Añadir fragmento</button>
          <button type="button" disabled={cargando || candidatos.length <= 3} onClick={() => setCandidatos((p) => p.slice(0,-1))}>Quitar último</button>
          <button type="submit" className="primary" disabled={cargando}>{cargando ? 'Ejecutando SciBERT y M/S…' : 'Analizar cita'}</button>
        </div>
        {error && <p className="error-message" role="alert">{error}</p>}
      </form>
    </section>
    {respuesta && <section className="results-section" aria-live="polite">
      <div className="section-heading"><h2>Resultados de la inferencia</h2><span>{respuesta.dispositivo.toUpperCase()} · {respuesta.tokens_ab} tokens AB</span></div>
      <p className="field-help">Recuperador: {respuesta.modelo_recuperacion} · SciBERT {respuesta.revision_scibert.slice(0,12)}</p>
      <h3>Top-3 recuperados</h3>
      <ol className="fragment-list">{respuesta.top3.map((f) => <li key={f.chunk_id}>
        <div><strong>{f.chunk_id} · {f.seccion || 'Sin sección'}</strong><span className="score">Coseno {f.similitud_coseno.toFixed(4)}</span></div>
        <p>{f.texto}</p><p className="field-help">Perfil: {f.perfil}</p>
      </li>)}</ol>
      <h3>Clasificación de las nueve funciones</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', gap: '1rem' }}>
        {(['M','S'] as const).map((pista) => {
          const r = respuesta.clasificadores[pista];
          return <article key={pista} style={{ padding: '1rem', border: '1px solid #d6dded', borderRadius: '12px' }}>
            <h3>Modelo {pista}</h3><p><strong>{r.clase}</strong> · {percent(r.probabilidad)}</p>
            <p className="field-help">{r.ajuste_ph ? 'Con ajuste PH' : 'Sin ajuste PH'}</p>
            {r.probabilidades.map((p) => <div key={p.clase} style={{ marginBottom: '.7rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}><span>{p.clase}</span><span>{percent(p.probabilidad)}</span></div>
              <div style={{ height: 7, background: '#e8ecf6', borderRadius: 10, overflow: 'hidden' }}><div style={{ height: '100%', width: `${Math.min(p.probabilidad * 100,100)}%`, background: '#3150e7' }} /></div>
            </div>)}
          </article>;
        })}
      </div>
      <p className="notice" role="note">{respuesta.aviso} Este caso ilustrativo no sustituye la evaluación de calidad sobre un conjunto independiente.</p>
    </section>}
  </>;
}
