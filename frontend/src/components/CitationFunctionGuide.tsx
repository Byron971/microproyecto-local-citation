import { meanings } from '../citationFunctions';

const titles: Record<string, string> = {
  Background: 'Contexto',
  Gap: 'Limitación o pregunta pendiente',
  Basis: 'Base conceptual',
  Comparison: 'Comparación',
  Application: 'Aplicación',
  'Improvement / Modification': 'Mejora o modificación',
  Evidence: 'Respaldo',
  'Identification of the Originator': 'Fuente original',
  'Further Reading': 'Lectura adicional',
};

export function CitationFunctionGuide() {
  return (
    <div className="result-info-surface citation-guide">
      <h4>Qué significan las nueve funciones</h4>
      <p className="detail-caption">
        Cada función describe el papel de la cita en el texto. Los nombres en inglés coinciden con
        las etiquetas de la puntuación.
      </p>
      <dl className="citation-definitions">
        {Object.entries(meanings).map(([name, meaning]) => (
          <div key={name}>
            <dt>
              <span className="citation-function-title">{titles[name] || name}</span>
              <span className="citation-function-name" lang="en">
                {name}
              </span>
            </dt>
            <dd>{meaning}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
