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
        </>
      )}
    </section>
  );
}

export function CommercialDetails({ result }: { result: CommercialClassification }) {
  return (
    <section className="analysis-detail-section" aria-label="Detalles del proveedor">
      <h4>Clasificación comercial</h4>
      <dl className="analysis-facts">
        <div>
          <dt>Proveedor</dt>
          <dd>{result.proveedor}</dd>
        </div>
        <div>
          <dt>Modelo efectivo</dt>
          <dd>{result.modelo_efectivo}</dd>
        </div>
        <div className="analysis-fact-wide">
          <dt>Información enviada</dt>
          <dd>Contexto de la cita, título y resumen del artículo.</dd>
        </div>
      </dl>
    </section>
  );
}

export function CommercialTechnicalDetails({ result }: { result: CommercialClassification }) {
  return (
    <dl className="technical-facts">
      <div>
        <dt>Perfil comercial</dt>
        <dd>
          <code>{result.perfil}</code>
        </dd>
      </div>
      <div>
        <dt>SHA-256 de instrucciones</dt>
        <dd>
          <code>{result.sha256_prompts}</code>
        </dd>
      </div>
    </dl>
  );
}
