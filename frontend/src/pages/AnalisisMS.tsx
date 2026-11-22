import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { errorMessage, request } from '../api';

import { ScientificResults, type Respuesta } from '../components/ScientificResults';
type Candidato = { chunk_id: string; texto: string; seccion: string };

const DEMO = {
  contexto:
    'Previous studies TARGETCIT introduced a neural approach for scientific document classification. We compare our architecture against this earlier approach.',
  titulo: 'Neural Methods for Scientific Text Classification',
  abstract:
    'This study investigates neural representations for classification of scientific documents and reports empirical results across several corpora.',
  candidatos: [
    {
      chunk_id: 'p00001',
      seccion: 'Methods',
      texto:
        'We train a neural encoder with a classification objective over labeled scientific documents.',
    },
    {
      chunk_id: 'p00002',
      seccion: 'Results',
      texto: 'The classifier improves macro F1 against a lexical baseline on the validation split.',
    },
    {
      chunk_id: 'p00003',
      seccion: 'Conclusion',
      texto:
        'Our experiments suggest that contextual embeddings can support scientific document classification.',
    },
    {
      chunk_id: 'p00004',
      seccion: 'Related Work',
      texto:
        'Earlier methods use lexical features and term frequency for classification of scholarly articles.',
    },
  ],
};

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

  async function cargarCasoReal(e: ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    try {
      if (archivo.size > 1024 * 1024) {
        throw new Error('El archivo supera 1 MB.');
      }
      const datos = JSON.parse(await archivo.text());
      if (
        typeof datos.contexto !== 'string' ||
        datos.contexto.split('TARGETCIT').length !== 2 ||
        typeof datos.titulo !== 'string' ||
        typeof datos.abstract !== 'string' ||
        !datos.titulo.trim() ||
        !datos.abstract.trim() ||
        !Array.isArray(datos.candidatos) ||
        datos.candidatos.length < 3 ||
        datos.candidatos.length > 100
      ) {
        throw new Error('El JSON no tiene el formato esperado.');
      }

      const nuevos = datos.candidatos.map((c: any) => {
        if (
          typeof c.chunk_id !== 'string' ||
          typeof c.texto !== 'string' ||
          !c.chunk_id.trim() ||
          !c.texto.trim()
        ) {
          throw new Error('Hay fragmentos sin ID o texto válido.');
        }
        return {
          chunk_id: c.chunk_id,
          texto: c.texto,
          seccion: String(c.seccion ?? ''),
        };
      });

      if (new Set(nuevos.map((c: Candidato) => c.chunk_id)).size !== nuevos.length) {
        throw new Error('Hay identificadores duplicados.');
      }

      controller.current?.abort();
      setContexto(datos.contexto);
      setTitulo(datos.titulo);
      setAbstract(datos.abstract);
      setCandidatos(nuevos);
      setRespuesta(null);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar el JSON.');
    } finally {
      e.target.value = '';
    }
  }
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
    setCandidatos((prev) => prev.map((c, j) => (j === i ? { ...c, [campo]: valor } : c)));
  }
  async function ejecutar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (contexto.split('TARGETCIT').length !== 2 || !titulo.trim() || !abstract.trim()) {
      setError('Se requiere un único TARGETCIT, título y abstract.');
      return;
    }
    if (
      candidatos.length < 3 ||
      candidatos.some((c) => !c.texto.trim() || !c.chunk_id.trim()) ||
      new Set(candidatos.map((c) => c.chunk_id.trim())).size !== candidatos.length
    ) {
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
        body: JSON.stringify({
          contexto: contexto.trim(),
          titulo: titulo.trim(),
          abstract: abstract.trim(),
          candidatos,
        }),
        signal: actual.signal,
      });
      if (!actual.signal.aborted) {
        if (
          !Array.isArray(resultado.top3) ||
          resultado.top3.length !== 3 ||
          resultado.clasificadores.M.probabilidades.length !== 9 ||
          resultado.clasificadores.S.probabilidades.length !== 9
        ) {
          throw new Error('La respuesta no tiene tres fragmentos y nueve categorías por modelo.');
        }
        setRespuesta(resultado);
      }
    } catch (err) {
      if (!actual.signal.aborted)
        setError(
          err instanceof Error && err.message.startsWith('La respuesta')
            ? err.message
            : errorMessage(err),
        );
    } finally {
      if (!actual.signal.aborted) setCargando(false);
    }
  }

  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">Análisis manual avanzado · SciBERT + M/S</span>
          <h1>Recuperación y función de la cita</h1>
          <p>
            Recupera tres fragmentos del artículo citado y compara nueve funciones retóricas con los
            modelos M y S.
          </p>
        </div>
      </div>
      <p className="notice" role="note">
        Prototipo experimental. Los fragmentos se suministran manualmente y deben pertenecer al
        mismo artículo citado. Los valores softmax no son probabilidades calibradas de acierto; la
        relevancia Top-3 y la precisión científica no están certificadas aquí.
      </p>
      <section className="workspace" aria-label="Análisis científico M/S">
        <form onSubmit={ejecutar}>
          <div className="form-actions">
            <button type="button" onClick={ejemplo} disabled={cargando}>
              Cargar ejemplo ilustrativo
            </button>
            <label htmlFor="ms-json">Cargar caso real JSON</label>
            <input
              id="ms-json"
              type="file"
              accept=".json,application/json"
              disabled={cargando}
              onChange={cargarCasoReal}
            />
          </div>
          <label htmlFor="ms-contexto">Contexto académico en inglés (TARGETCIT una vez)</label>
          <textarea
            id="ms-contexto"
            lang="en"
            rows={4}
            maxLength={4000}
            required
            value={contexto}
            onChange={(e) => setContexto(e.target.value)}
            placeholder="Earlier work TARGETCIT showed..."
          />
          <label htmlFor="ms-titulo">Título del artículo citado</label>
          <input
            id="ms-titulo"
            lang="en"
            maxLength={600}
            required
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
          />
          <label htmlFor="ms-abstract">Abstract del artículo citado</label>
          <textarea
            id="ms-abstract"
            lang="en"
            rows={4}
            maxLength={12000}
            required
            value={abstract}
            onChange={(e) => setAbstract(e.target.value)}
          />
          <h2>Fragmentos candidatos</h2>
          <p className="field-help">
            Introduce al menos tres fragmentos del mismo artículo. SciBERT seleccionará
            automáticamente los Top-3.
          </p>
          {candidatos.map((c, i) => (
            <div
              key={i}
              style={{
                border: '1px solid #d6dded',
                borderRadius: '12px',
                padding: '1rem',
                marginBottom: '1rem',
              }}
            >
              <h3>Fragmento {i + 1}</h3>
              <label htmlFor={`ms-id-${i}`}>Identificador</label>
              <input
                id={`ms-id-${i}`}
                required
                maxLength={120}
                value={c.chunk_id}
                onChange={(e) => actualizar(i, 'chunk_id', e.target.value)}
              />
              <label htmlFor={`ms-seccion-${i}`}>Sección</label>
              <input
                id={`ms-seccion-${i}`}
                maxLength={200}
                value={c.seccion}
                onChange={(e) => actualizar(i, 'seccion', e.target.value)}
              />
              <label htmlFor={`ms-texto-${i}`}>Texto del fragmento</label>
              <textarea
                id={`ms-texto-${i}`}
                lang="en"
                required
                maxLength={5000}
                rows={3}
                value={c.texto}
                onChange={(e) => actualizar(i, 'texto', e.target.value)}
              />
            </div>
          ))}
          <div className="form-actions">
            <button
              type="button"
              disabled={cargando || candidatos.length >= 100}
              onClick={() =>
                setCandidatos((p) => [
                  ...p,
                  { chunk_id: `p${String(p.length + 1).padStart(5, '0')}`, seccion: '', texto: '' },
                ])
              }
            >
              Añadir fragmento
            </button>
            <button
              type="button"
              disabled={cargando || candidatos.length <= 3}
              onClick={() => setCandidatos((p) => p.slice(0, -1))}
            >
              Quitar último
            </button>
            <button type="submit" className="primary" disabled={cargando}>
              {cargando ? 'Ejecutando SciBERT y M/S…' : 'Analizar cita'}
            </button>
          </div>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>
      {respuesta && <ScientificResults respuesta={respuesta} />}
    </>
  );
}
