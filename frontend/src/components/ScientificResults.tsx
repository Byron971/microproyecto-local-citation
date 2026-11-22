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
const meanings: Record<string, string> = {
  Background: 'Presenta información de contexto sobre el tema.',
  Gap: 'Señala una limitación o una pregunta pendiente en trabajos anteriores.',
  Basis: 'Usa el trabajo citado como base conceptual para la investigación.',
  Comparison: 'Compara métodos, datos o resultados con otros trabajos.',
  Application: 'Utiliza un método, técnica o herramienta sin modificarlo.',
  'Improvement / Modification': 'Adapta, amplía o mejora un método del trabajo citado.',
  Evidence: 'Aporta respaldo para una afirmación, decisión o resultado.',
  'Identification of the Originator': 'Reconoce la fuente original de una idea o método.',
  'Further Reading': 'Remite a lecturas con información adicional.',
};
const percent = (x: number) => `${(x * 100).toFixed(2)} %`;
export function ScientificResults({
  respuesta,
  variante,
  fuente,
}: {
  respuesta: Respuesta;
  variante?: 'M' | 'S';
  fuente?: string;
}) {
  return (
    <section className="results-section" aria-live="polite">
      <h2>Resultados del análisis</h2>
      <h3>Fragmentos relacionados del artículo citado</h3>
      <p className="field-help">
        Son candidatos relacionados; no prueban por sí solos la afirmación ni verifican que la cita
        sea correcta.
      </p>
      <ol className="fragment-list">
        {respuesta.top3.map((fragment, index) => (
          <li key={fragment.chunk_id}>
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
      <h3>Función predicha de la cita</h3>
      <p className="field-help">
        Las puntuaciones softmax indican cómo el modelo reparte su salida entre funciones. No son
        porcentajes de acierto.
      </p>
      <div className="classifier-results">
        {(variante ? [variante] : (['M', 'S'] as const)).map((track) => {
          const classifier = respuesta.clasificadores[track];
          return (
            <article key={track} className="classifier-result">
              <h3>Modelo {track}</h3>
              <p>
                <strong>{classifier.clase}</strong> · puntuación softmax{' '}
                {percent(classifier.probabilidad)}
              </p>
              <p>
                {meanings[classifier.clase] || 'Consulta la definición de esta función en la guía.'}
              </p>
              {classifier.probabilidades.map((score) => (
                <div key={score.clase} className="function-score">
                  <div className="function-score-label">
                    <span>{score.clase}</span>
                    <span>{percent(score.probabilidad)}</span>
                  </div>
                  <div className="function-score-track">
                    <div
                      style={{ width: `${Math.min(Math.max(score.probabilidad * 100, 0), 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </article>
          );
        })}
      </div>
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
        <p>
          El servicio calcula M y S; se muestra{' '}
          {variante ? `la variante ${variante}` : 'ambas variantes'}. Ajuste PH:{' '}
          {(['M', 'S'] as const)
            .map((track) => `${track} ${respuesta.clasificadores[track].ajuste_ph ? 'sí' : 'no'}`)
            .join(', ')}
          .
        </p>
      </details>
    </section>
  );
}
