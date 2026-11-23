import { AnalysisDetails } from './AnalysisDetails';
import { useId, useRef, useState, type KeyboardEvent } from 'react';
import type { TruncationInfo } from './ArticlePicker';
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
  truncation,
  variante,
  fuente,
  commercialSelected,
  commercial,
  commercialPending,
  hideHeading,
}: {
  respuesta: Respuesta;
  truncation?: TruncationInfo;
  variante?: 'M' | 'S';
  fuente?: string;
  commercialSelected?: boolean;
  commercial?: CommercialClassification;
  commercialPending?: boolean;
  hideHeading?: boolean;
}) {
  const id = useId();
  const [activeTab, setActiveTab] = useState(0);
  const tabs = ['Puntuación', 'Detalles del análisis', 'Ayuda'];
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  function navigateTabs(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next =
      event.key === 'ArrowRight'
        ? (index + 1) % tabs.length
        : event.key === 'ArrowLeft'
          ? (index + tabs.length - 1) % tabs.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? tabs.length - 1
              : undefined;
    if (next === undefined) return;
    event.preventDefault();
    setActiveTab(next);
    buttons.current[next]?.focus();
  }
  return (
    <section className="results-section" aria-live="polite">
      {!hideHeading && <h2>Resultados del análisis</h2>}
      <h3>Fragmentos relacionados del artículo citado</h3>
      <p className="field-help">
        Son candidatos relacionados; no prueban por sí solos la afirmación ni verifican que la cita
        sea correcta.
      </p>
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
      <h3 id={`${id}-heading`}>Función predicha de la cita</h3>
      <div className="result-tabs" role="tablist" aria-labelledby={`${id}-heading`}>
        {tabs.map((label, index) => (
          <button
            key={label}
            type="button"
            role="tab"
            id={`${id}-tab-${index}`}
            aria-controls={`${id}-panel-${index}`}
            aria-selected={activeTab === index}
            tabIndex={activeTab === index ? 0 : -1}
            ref={(element) => {
              buttons.current[index] = element;
            }}
            onClick={() => setActiveTab(index)}
            onKeyDown={(event) => navigateTabs(event, index)}
          >
            {label}
          </button>
        ))}
      </div>
      <div
        className="result-tab-panel"
        role="tabpanel"
        id={`${id}-panel-0`}
        aria-labelledby={`${id}-tab-0`}
        hidden={activeTab !== 0}
        tabIndex={0}
      >
        {commercialSelected ? (
          <CommercialResults result={commercial} pending={commercialPending} />
        ) : (
          <>
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
      </div>
      <div
        className="result-tab-panel analysis-help"
        role="tabpanel"
        id={`${id}-panel-1`}
        aria-labelledby={`${id}-tab-1`}
        hidden={activeTab !== 1}
        tabIndex={0}
      >
        <AnalysisDetails
          respuesta={respuesta}
          truncation={truncation}
          variante={variante}
          commercialSelected={commercialSelected}
          commercial={commercial}
        />
      </div>
      <div
        className="result-tab-panel analysis-help"
        role="tabpanel"
        id={`${id}-panel-2`}
        aria-labelledby={`${id}-tab-2`}
        hidden={activeTab !== 2}
        tabIndex={0}
      >
        <h4>Qué significan las nueve funciones</h4>
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
      </div>
    </section>
  );
}
