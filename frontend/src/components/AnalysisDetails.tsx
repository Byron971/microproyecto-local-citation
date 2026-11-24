import { useId } from 'react';
import type { Respuesta } from './ScientificResults';
import type { TruncationInfo } from './ArticlePicker';
import {
  CommercialDetails,
  CommercialTechnicalDetails,
  type CommercialClassification,
} from './CommercialResults';

export function AnalysisDetails({
  respuesta,
  truncation,
  variante,
  commercialSelected,
  commercial,
}: {
  respuesta: Respuesta;
  truncation?: TruncationInfo;
  variante?: 'M' | 'S';
  commercialSelected?: boolean;
  commercial?: CommercialClassification;
}) {
  const id = useId();
  const retrieval = respuesta.modelo_recuperacion?.toLowerCase().includes('scibert')
    ? 'SciBERT'
    : respuesta.modelo_recuperacion || 'No informado';
  const classifier = commercialSelected
    ? 'Comercial'
    : variante
      ? `Encoder SciBERT — ${variante}`
      : 'Encoder SciBERT — M y S';
  const device =
    respuesta.dispositivo === 'cpu'
      ? 'CPU'
      : respuesta.dispositivo === 'cuda'
        ? 'GPU (CUDA)'
        : respuesta.dispositivo;
  return (
    <div className="result-info-surface analysis-details">
      <section className="analysis-detail-section" aria-label="Resumen del análisis">
        <h4>Cómo se obtuvo el resultado</h4>
        <dl className="analysis-facts">
          <div>
            <dt>Recuperación de fragmentos</dt>
            <dd>{retrieval}</dd>
          </div>
          <div>
            <dt>Clasificación de la cita</dt>
            <dd>{classifier}</dd>
          </div>
        </dl>
        <p className="detail-caption">
          Se calculan las variantes M y S.{' '}
          {commercialSelected
            ? 'La función mostrada corresponde al modelo comercial.'
            : variante
              ? `Se muestra la variante ${variante}.`
              : 'Se muestran ambas variantes.'}
        </p>
      </section>
      {truncation?.aplicado && (
        <section className="analysis-scope-note" aria-label="Alcance del texto analizado">
          <h4>Alcance del texto analizado</h4>
          <p>
            Se usaron{' '}
            <strong>
              {truncation.fragmentos_analizados} de {truncation.fragmentos_originales} fragmentos
            </strong>{' '}
            y {truncation.caracteres_analizados.toLocaleString('es')} de{' '}
            {truncation.caracteres_originales.toLocaleString('es')} caracteres del artículo y sus
            metadatos.
          </p>
          <p>
            {truncation.texto_recortado
              ? 'El recorte conserva el inicio en su orden original; el último fragmento puede ser parcial.'
              : 'Los metadatos se recortaron a los límites del análisis.'}
          </p>
        </section>
      )}
      <section className="analysis-detail-section" aria-labelledby={`${id}-fragments`}>
        <h4 id={`${id}-fragments`}>Fragmentos recuperados</h4>
        <p className="detail-caption" id={`${id}-similarity`}>
          Similitud coseno con el contexto. Un valor mayor no demuestra que el fragmento sea
          correcto.
        </p>
        <table className="fragment-metadata" aria-describedby={`${id}-similarity`}>
          <caption className="sr-only">
            Sección y similitud de los tres fragmentos recuperados
          </caption>
          <thead>
            <tr>
              <th scope="col">Fragmento</th>
              <th scope="col">Sección del artículo</th>
              <th scope="col">Similitud</th>
            </tr>
          </thead>
          <tbody>
            {respuesta.top3.map((fragment, index) => (
              <tr key={fragment.chunk_id}>
                <th scope="row">
                  <a href={`#fragment-${index + 1}`}>Fragmento {index + 1}</a>
                </th>
                <td>{fragment.seccion || 'Sin sección identificada'}</td>
                <td className="similarity-value">{fragment.similitud_coseno.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {commercialSelected && commercial && <CommercialDetails result={commercial} />}
      <p className="analysis-interpretation">
        Las similitudes y puntuaciones del modelo no validan la precisión ni que la cita sea
        correcta.
      </p>
      <details className="analysis-technical">
        <summary>Ver detalles técnicos</summary>
        <dl className="technical-facts">
          {device && (
            <div>
              <dt>Procesamiento de SciBERT</dt>
              <dd>{device}</dd>
            </div>
          )}
          {Number.isFinite(respuesta.tokens_ab) && (
            <div>
              <dt>Entrada de M/S</dt>
              <dd>{respuesta.tokens_ab} tokens</dd>
            </div>
          )}

          <div>
            <dt>Método de recuperación</dt>
            <dd>
              <code>{respuesta.modelo_recuperacion}</code>
            </dd>
          </div>
          <div>
            <dt>Revisión de SciBERT</dt>
            <dd>
              <code>{respuesta.revision_scibert}</code>
            </dd>
          </div>
          {!commercialSelected && (
            <div>
              <dt>Ajuste PH</dt>
              <dd>
                {(['M', 'S'] as const)
                  .map(
                    (track) =>
                      `${track}: ${respuesta.clasificadores[track].ajuste_ph === true ? 'sí' : respuesta.clasificadores[track].ajuste_ph === false ? 'no' : 'no informado'}`,
                  )
                  .join(' · ')}
              </dd>
            </div>
          )}
          {respuesta.top3.map((fragment, index) => (
            <div key={fragment.chunk_id}>
              <dt>Identificador del fragmento {index + 1}</dt>
              <dd>
                <code>{fragment.chunk_id}</code>
                <span className="technical-profile">
                  Perfil: {fragment.perfil || 'no indicado'}
                </span>
              </dd>
            </div>
          ))}
        </dl>
        {!commercialSelected && <p>Puntuaciones softmax sin calibración de acierto.</p>}
        {respuesta.aviso && <p>{respuesta.aviso}</p>}
        {commercialSelected && commercial && <CommercialTechnicalDetails result={commercial} />}
      </details>
    </div>
  );
}
