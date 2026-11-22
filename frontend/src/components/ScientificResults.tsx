import { meanings } from '../citationFunctions';
import { CommercialResults, type CommercialClassification } from './CommercialResults';
type Candidato = { chunk_id: string; texto: string; seccion: string };
type Puntuacion = { clase: string; probabilidad: number };
type Clasificador = {
  clase: string;
  indice: number;
  probabilidad: number;
  ajuste_ph: boolean;
  probabilidades: Puntuacion[];
};
export type Respuesta = {
  modelo_recuperacion: string;
  revision_scibert: string;
  dispositivo: string;
  tokens_ab: number;
  top3: (Candidato & { posicion: number; similitud_coseno: number; perfil: string })[];
  clasificadores: { M: Clasificador; S: Clasificador };
  aviso: string;
};
const percent = (x: number) => `${(x * 100).toFixed(2)} %`;
export function ScientificResults({
  respuesta,
  variante,
  fuente,
  commercialSelected,
  commercial,
  commercialPending,
}: {
  respuesta: Respuesta;
  variante?: 'M' | 'S';
  fuente?: string;
  commercialSelected?: boolean;
  commercial?: CommercialClassification;
  commercialPending?: boolean;
}) {
  return (
    <section className="results-section" aria-live="polite">
      <h2>Resultados del análisis</h2>
      <h3>Fragmentos relacionados del artículo citado</h3>
      <p className="field-help">
        Son candidatos relacionados; no prueban por sí solos la afirmación ni verifican que la cita
        sea correcta.
      </p>
      <nav className="fragment-overview" aria-label="Secciones del Top-3">
        {respuesta.top3.map((fragment, index) => (
          <a key={fragment.chunk_id} href={`#fragment-${index + 1}`}>
            <span>{index + 1}</span>
            {fragment.seccion || 'Sin sección identificada'}
          </a>
        ))}
      </nav>
      <ol className="fragment-list">
        {respuesta.top3.map((fragment, index) => (
          <li key={fragment.chunk_id} id={`fragment-${index + 1}`} tabIndex={-1}>
            <strong>
              {index + 1}. {fragment.seccion || 'Sin sección identificada'}
            </strong>
            <p>{fragment.texto}</p>
            {fuente && (
              <a
                href={fuente}
                target="_blank"
                rel="noreferrer"
                aria-label={`Ver fuente del fragmento ${index + 1}`}
              >
                Ver fuente
              </a>
            )}
          </li>
        ))}
      </ol>
      {commercialSelected ? (
        <CommercialResults result={commercial} pending={commercialPending} />
      ) : (
        <>
          <h3>Función predicha de la cita</h3>
          <p className="field-help">
            Las barras muestran cómo el clasificador reparte su puntuación entre las nueve
            funciones. No son porcentajes de acierto.
          </p>
          <div className="classifier-results">
            {(variante ? [variante] : (['M', 'S'] as const)).map((track) => {
              const classifier = respuesta.clasificadores[track];
              return (
                <article key={track} className="classifier-result">
                  <h3>Modelo {track}</h3>
                  <p className="prediction-summary">
                    <strong>{classifier.clase}</strong> · puntuación del modelo{' '}
                    {percent(classifier.probabilidad)}
                  </p>
                  <p>
                    {meanings[classifier.clase] ||
                      'Consulta la definición de esta función en la guía.'}
                  </p>
                  {classifier.probabilidades.map((score) => (
                    <div
                      key={score.clase}
                      className={`function-score ${score.clase === classifier.clase ? 'predicted-score' : ''}`}
                    >
                      <div className="function-score-label">
                        <span>{score.clase}</span>
                        <span>{percent(score.probabilidad)}</span>
                      </div>
                      <div className="function-score-track" aria-hidden="true">
                        <div
                          style={{
                            width: `${Math.min(Math.max(score.probabilidad * 100, 0), 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </article>
              );
            })}
          </div>
        </>
      )}
      <details className="analysis-help">
        <summary>Qué significan las nueve funciones</summary>
        <dl>
          {Object.entries(meanings).map(([name, meaning]) => (
            <div key={name}>
              <dt>
                <strong>{name}</strong>
              </dt>
              <dd>{meaning}</dd>
            </div>
          ))}
        </dl>
      </details>
      <details className="analysis-help">
        <summary>Detalles del análisis</summary>
        <p>
          Recuperador: {respuesta.modelo_recuperacion} · revisión SciBERT:{' '}
          {respuesta.revision_scibert}
        </p>
        <p>
          Dispositivo: {respuesta.dispositivo} · entrada AB: {respuesta.tokens_ab} tokens.
        </p>
        <p>{respuesta.aviso}</p>
        <ul>
          {respuesta.top3.map((fragment) => (
            <li key={fragment.chunk_id}>
              {fragment.chunk_id} · similitud coseno {fragment.similitud_coseno.toFixed(4)} · perfil{' '}
              {fragment.perfil || 'no indicado'}
            </li>
          ))}
        </ul>
        {commercialSelected ? (
          <p>
            SciBERT recupera los fragmentos y calcula M/S. Se muestra la clasificación comercial
            seleccionada, que usa contexto, título y resumen.
          </p>
        ) : (
          <p>
            Puntuaciones softmax sin calibración de acierto. El servicio calcula M y S; se muestra{' '}
            {variante ? `la variante ${variante}` : 'ambas variantes'}. Ajuste PH:{' '}
            {(['M', 'S'] as const)
              .map((track) => `${track} ${respuesta.clasificadores[track].ajuste_ph ? 'sí' : 'no'}`)
              .join(', ')}
            .
          </p>
        )}
      </details>
    </section>
  );
}
