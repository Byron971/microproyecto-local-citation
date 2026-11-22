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
export function CommercialResults({ result }: { result?: CommercialClassification }) {
  return (
    <section aria-label="Clasificación comercial">
      <h3>Función predicha de la cita</h3>
      <h3>GPT-6.1 Sol</h3>
      {!result ? (
        <p>Sin clasificación comercial todavía. Los fragmentos recuperados se conservan.</p>
      ) : (
        <>
          <p>
            <strong>{result.clase || result.abstencion}</strong>
          </p>
          <p>
            Estos puntajes los genera el modelo; no son probabilidades calibradas ni porcentajes de
            acierto.
          </p>
          {result.puntuaciones.map((score) => (
            <div className="function-score" key={score.clase}>
              <div className="function-score-label">
                <span>{score.clase}</span>
                <span>{score.valor.toFixed(3)}</span>
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
