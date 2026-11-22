import { meanings } from '../citationFunctions';
export type CommercialClassification = {
  paper_id: string;
  version_contenido: string;
  proveedor: string;
  modelo_solicitado: string;
  modelo_efectivo: string;
  perfil: string;
  sha256_prompts: string;
  clase: string | null;
  abstencion: string | null;
  puntuaciones: { clase: string; valor: number }[];
};
export function CommercialResults({
  result,
  pending,
}: {
  result?: CommercialClassification;
  pending?: boolean;
}) {
  return (
    <section className="commercial-results classifier-result" aria-label="Clasificación comercial">
      <h3>Función predicha de la cita</h3>
      <p className="model-identity">GPT-6.1 Sol · OpenAI</p>
      {!result ? (
        <p role="status">
          {pending
            ? 'Top-3 listo. Esperando la clasificación de OpenAI…'
            : 'Sin clasificación comercial todavía. Los fragmentos recuperados se conservan.'}
        </p>
      ) : (
        <>
          <p className="prediction-summary">
            <strong>{result.clase || result.abstencion || 'Sin función definida'}</strong>
          </p>
          <p>
            {result.clase
              ? meanings[result.clase] || 'Consulta la guía de funciones.'
              : 'El modelo no distingue una función única para esta cita.'}
          </p>
          <p>
            Estos puntajes los genera el modelo; no son probabilidades calibradas ni porcentajes de
            acierto.
          </p>
          {result.puntuaciones.map((score) => (
            <div
              className={`function-score ${score.clase === result.clase ? 'predicted-score' : ''}`}
              key={score.clase}
            >
              <div className="function-score-label">
                <span>{score.clase}</span>
                <span>{score.valor.toFixed(3)}</span>
              </div>
              <div className="function-score-track" aria-hidden="true">
                <div style={{ width: `${Math.min(1, Math.max(0, score.valor)) * 100}%` }} />
              </div>
            </div>
          ))}
          <details className="analysis-help">
            <summary>Detalles del proveedor</summary>
            <p>
              Proveedor: {result.proveedor} · Modelo efectivo: {result.modelo_efectivo}
            </p>
            <p>
              Entrada: contexto, título y resumen. Los fragmentos Top-3 se recuperan con SciBERT.
            </p>
            <p>
              Perfil: {result.perfil} · SHA-256 de instrucciones: {result.sha256_prompts}
            </p>
          </details>
        </>
      )}
    </section>
  );
}
