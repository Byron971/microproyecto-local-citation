import { useEffect, useState, type ReactNode } from 'react';
import { request, errorMessage } from '../api';
interface Histogram {
  bordes: number[];
  conteos: number[];
}
interface Insights {
  generado_en: string;
  dataset: { contextos: number; articulos: number; particiones: Record<string, number> };
  calidad: { comprobacion: string; cantidad: number }[];
  longitudes: {
    resumen: { texto: string; mediana: number; percentil_95: number; maximo: number }[];
    histograma_contextos: Histogram;
    histograma_resumenes: Histogram;
    othercit_promedio: number;
  };
  terminos: {
    unigramas: { termino: string; frecuencia: number }[];
    bigramas: { termino: string; frecuencia: number }[];
  };
  similitud: {
    muestra: number;
    porcentaje_positivo_mayor: number;
    media_positivos: number;
    media_negativos: number;
    histograma_positivos: Histogram;
    histograma_negativos: Histogram;
  };
  integridad_particiones: {
    particiones: string;
    citantes_compartidos: number;
    pares_compartidos: number;
  }[];
  mas_citados: { paper_id: string; titulo: string; contextos: number }[];
  modelo: {
    particion: string;
    consultas: number;
    vocabulario: number;
    techo_recuperacion: number;
    curva: { k: number; recall: number; mrr: number }[];
  };
  negativos: null | {
    consultas: number;
    top_n: number;
    similitud_media: Record<string, number>;
    auc: Record<string, number>;
    aleatorios_sin_terminos_comunes: number;
    aleatorios_bajo_media_positiva: number;
  };
}
let cached: Promise<Insights> | undefined;
function getInsights() {
  cached ??= request<Insights>('/api/insights').catch((error) => {
    cached = undefined;
    throw error;
  });
  return cached;
}
const number = (n: number) => n.toLocaleString('es', { maximumFractionDigits: 3 });
function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="analytics-panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
function DataTable({
  headings,
  rows,
  caption,
}: {
  headings: string[];
  rows: (string | number)[][];
  caption: string;
}) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {headings.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{typeof cell === 'number' ? number(cell) : cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Stats({ items }: { items: [string, number][] }) {
  return (
    <dl className="stats-strip">
      {items.map(([name, value]) => (
        <div key={name}>
          <dt>{name}</dt>
          <dd>{number(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
function Bars({ values }: { values: { label: string; value: number }[] }) {
  const max = Math.max(...values.map((v) => v.value), 1e-9);
  return (
    <ol className="bar-chart">
      {values.map((v) => (
        <li key={v.label}>
          <span>{v.label}</span>
          <div className="bar-track">
            <span style={{ width: `${(v.value / max) * 100}%` }} />
          </div>
          <strong>{number(v.value)}</strong>
        </li>
      ))}
    </ol>
  );
}
function HistogramChart({
  series,
  title,
}: {
  series: { data: Histogram; label: string }[];
  title: string;
}) {
  const maxX = Math.max(...series.flatMap((s) => s.data.bordes));
  const maxY = Math.max(...series.flatMap((s) => s.data.conteos), 1);
  return (
    <figure className="histogram">
      <figcaption>{title}</figcaption>
      <svg viewBox="0 0 640 190" role="img" aria-label={title}>
        <line x1="40" y1="160" x2="620" y2="160" stroke="currentColor" />
        {series.map((s, n) => (
          <g key={s.label} fill={n ? '#4A5568' : '#2F4BE0'} opacity={series.length > 1 ? 0.6 : 1}>
            {s.data.conteos.map((v, i) => (
              <rect
                key={i}
                x={40 + (s.data.bordes[i] / maxX) * 580}
                y={160 - (v / maxY) * 140}
                width={Math.max(((s.data.bordes[i + 1] - s.data.bordes[i]) / maxX) * 580 - 1, 1)}
                height={(v / maxY) * 140}
              >
                <title>
                  {s.label}: {number(s.data.bordes[i])}–{number(s.data.bordes[i + 1])}, {number(v)}{' '}
                  casos
                </title>
              </rect>
            ))}
          </g>
        ))}
        <text x="40" y="183">
          0
        </text>
        <text x="600" y="183">
          {number(maxX)}
        </text>
        <text x="2" y="20">
          {number(maxY)}
        </text>
      </svg>
      <div className="chart-legend">
        {series.map((s, i) => (
          <span key={s.label}>
            <i style={{ background: i ? '#4A5568' : '#2F4BE0' }} />
            {s.label}
          </span>
        ))}
      </div>
      <details>
        <summary>Ver datos de la gráfica</summary>
        {series.map((s) => (
          <DataTable
            key={s.label}
            caption={s.label}
            headings={['Intervalo', s.label]}
            rows={s.data.conteos.map((n, i) => [
              `${number(s.data.bordes[i])}–${number(s.data.bordes[i + 1])}`,
              n,
            ])}
          />
        ))}
      </details>
    </figure>
  );
}
export function Analytics({ view }: { view: 'datos' | 'modelo' | 'negativos' }) {
  const [data, setData] = useState<Insights>();
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let current = true;
    setError('');
    getInsights()
      .then((value) => {
        if (current) setData(value);
      })
      .catch((err) => {
        if (current) setError(errorMessage(err));
      });
    return () => {
      current = false;
    };
  }, [retry]);
  const titles = {
    datos: 'El corpus, de cerca.',
    modelo: 'Qué recupera la línea base.',
    negativos: 'Aprender de los casos difíciles.',
  };
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">
            Estudio del recomendador ·{' '}
            {view === 'datos' ? 'Datos' : view === 'modelo' ? 'Desempeño' : 'Negativos'}
          </span>
          <h1>{titles[view]}</h1>
          <p>
            Información precalculada del estudio original. No cambia con el modelo seleccionado.
          </p>
        </div>
      </div>
      {error ? (
        <div className="error-message" role="alert">
          {error}
          <button onClick={() => setRetry((n) => n + 1)}>Reintentar</button>
        </div>
      ) : !data ? (
        <div className="skeleton-list" role="status" aria-label="Cargando estudio">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      ) : (
        <>
          <p className="data-date">Datos generados: {data.generado_en}</p>
          {view === 'datos' && (
            <>
              <Stats
                items={[
                  ['Contextos de cita', data.dataset.contextos],
                  ['Artículos', data.dataset.articulos],
                  ...Object.entries(data.dataset.particiones).map(([k, v]): [string, number] => [
                    `Consultas ${k}`,
                    v,
                  ]),
                ]}
              />
              <div className="analytics-grid">
                <Panel title="Longitud de los textos">
                  <p>
                    Longitudes medidas en palabras. Otras citas por contexto:{' '}
                    {number(data.longitudes.othercit_promedio)}.
                  </p>
                  <DataTable
                    caption="Longitudes"
                    headings={['Texto', 'Mediana', 'P95', 'Máximo']}
                    rows={data.longitudes.resumen.map((r) => [
                      r.texto,
                      r.mediana,
                      r.percentil_95,
                      r.maximo,
                    ])}
                  />
                  <HistogramChart
                    title="Longitud de los contextos"
                    series={[{ data: data.longitudes.histograma_contextos, label: 'Contextos' }]}
                  />
                  <HistogramChart
                    title="Longitud de los resúmenes"
                    series={[{ data: data.longitudes.histograma_resumenes, label: 'Resúmenes' }]}
                  />
                  <p className="field-help">
                    La distribución de resúmenes está recortada en el percentil 99; la tabla
                    conserva el máximo completo.
                  </p>
                </Panel>
                <Panel title="Calidad e integridad">
                  <DataTable
                    caption="Comprobaciones del corpus"
                    headings={['Comprobación', 'Casos']}
                    rows={data.calidad.map((r) => [r.comprobacion, r.cantidad])}
                  />
                  <h3>Separación de particiones</h3>
                  <DataTable
                    caption="Integridad de particiones"
                    headings={['Particiones', 'Citantes compartidos', 'Pares compartidos']}
                    rows={data.integridad_particiones.map((r) => [
                      r.particiones,
                      r.citantes_compartidos,
                      r.pares_compartidos,
                    ])}
                  />
                </Panel>
                <Panel title="Palabras más frecuentes">
                  <Bars
                    values={data.terminos.unigramas.map((r) => ({
                      label: r.termino,
                      value: r.frecuencia,
                    }))}
                  />
                </Panel>
                <Panel title="Bigramas más frecuentes">
                  <Bars
                    values={data.terminos.bigramas.map((r) => ({
                      label: r.termino,
                      value: r.frecuencia,
                    }))}
                  />
                </Panel>
                <Panel title="Señal léxica">
                  <p>
                    En {number(data.similitud.muestra)} consultas, el artículo citado supera al
                    aleatorio en {number(data.similitud.porcentaje_positivo_mayor)} % de los casos.
                    Medias: {number(data.similitud.media_positivos)} y{' '}
                    {number(data.similitud.media_negativos)}.
                  </p>
                  <HistogramChart
                    title="Distribución de similitud coseno"
                    series={[
                      { data: data.similitud.histograma_positivos, label: 'Artículo citado' },
                      { data: data.similitud.histograma_negativos, label: 'Artículo al azar' },
                    ]}
                  />
                </Panel>
                <Panel title="Los diez artículos más citados">
                  <Bars
                    values={data.mas_citados.map((r) => ({
                      label: `${r.paper_id} · ${r.titulo}`,
                      value: r.contextos,
                    }))}
                  />
                </Panel>
              </div>
            </>
          )}
          {view === 'modelo' && (
            <>
              <Stats
                items={[
                  ['Consultas evaluadas', data.modelo.consultas],
                  ['Vocabulario', data.modelo.vocabulario],
                  ['Recall@100', data.modelo.techo_recuperacion],
                ]}
              />
              <div className="analytics-grid">
                <Panel title="Recuperación por profundidad">
                  <p>
                    Partición: {data.modelo.particion}. Curva de la primera etapa TF-IDF, no una
                    evaluación del reordenador actual.
                  </p>
                  <svg
                    className="line-chart"
                    viewBox="0 0 640 250"
                    role="img"
                    aria-label="Curva de Recall y MRR entre K=1 y K=100"
                  >
                    <path d="M45 20v190h570" fill="none" stroke="currentColor" />
                    {[0, 0.25, 0.5, 0.75, 1].map((v) => (
                      <g key={v}>
                        <text x="4" y={214 - v * 190}>
                          {v}
                        </text>
                        <line
                          x1="45"
                          x2="615"
                          y1={210 - v * 190}
                          y2={210 - v * 190}
                          stroke="#dce1ed"
                        />
                      </g>
                    ))}
                    {(['recall', 'mrr'] as const).map((metric, i) => (
                      <polyline
                        key={metric}
                        points={data.modelo.curva
                          .map((p) => `${45 + (p.k / 100) * 570},${210 - p[metric] * 190}`)
                          .join(' ')}
                        fill="none"
                        stroke={i ? '#4A5568' : '#2F4BE0'}
                        strokeWidth="3"
                      />
                    ))}
                    <text x="45" y="239">
                      K = 1
                    </text>
                    <text x="570" y="239">
                      K = 100
                    </text>
                  </svg>
                  <p className="chart-legend">Azul: Recall@K · Gris: MRR@K</p>
                  <DataTable
                    caption="Curva de recuperación"
                    headings={['K', 'Recall@K', 'MRR@K']}
                    rows={data.modelo.curva.map((r) => [r.k, r.recall, r.mrr])}
                  />
                </Panel>
                <Panel title="Cómo leer estos resultados">
                  <p>
                    Recall indica si la cita real apareció entre los primeros K artículos. MRR da
                    más valor a encontrarla en las primeras posiciones.
                  </p>
                  <p>
                    El reordenador solo puede subir los candidatos que la primera etapa recupera.
                    Recall@100 = {number(data.modelo.techo_recuperacion)} es el techo de este
                    conjunto de candidatos.
                  </p>
                  <p>
                    Recuperar más artículos no garantiza que las primeras posiciones sean mejores.
                    Estas cifras pertenecen al experimento original y no deben atribuirse a modelos
                    futuros.
                  </p>
                </Panel>
              </div>
            </>
          )}
          {view === 'negativos' &&
            (data.negativos ? (
              <>
                <Stats
                  items={[
                    ['Consultas de validación', data.negativos.consultas],
                    ['Candidatos por consulta', data.negativos.top_n],
                  ]}
                />
                <div className="analytics-grid">
                  <Panel title="Similitud media">
                    <Bars
                      values={Object.entries(data.negativos.similitud_media).map(
                        ([label, value]) => ({ label, value }),
                      )}
                    />
                    <p>
                      Los negativos duros son candidatos cercanos recuperados por TF-IDF; los
                      aleatorios se eligen del corpus.
                    </p>
                  </Panel>
                  <Panel title="Separación por similitud (AUC)">
                    <Bars
                      values={Object.entries(data.negativos.auc).map(([label, value]) => ({
                        label: label.replaceAll('_', ' '),
                        value,
                      }))}
                    />
                    <p>
                      AUC = 0.5 corresponde a la separación al azar. El contraste muestra por qué
                      los negativos aleatorios pueden facilitar artificialmente la tarea.
                    </p>
                  </Panel>
                  <Panel title="Qué cambia al entrenar">
                    <p>
                      {number(data.negativos.aleatorios_sin_terminos_comunes)} % de negativos
                      aleatorios no comparte términos con la consulta;{' '}
                      {number(data.negativos.aleatorios_bajo_media_positiva)} % queda por debajo de
                      la media positiva.
                    </p>
                    <p>
                      En inferencia, el reordenador ve candidatos temáticamente cercanos. La calidad
                      frente a negativos aleatorios no demuestra la misma calidad frente a
                      candidatos difíciles.
                    </p>
                  </Panel>
                </div>
              </>
            ) : (
              <p className="notice">
                El diagnóstico de negativos no está disponible en esta versión del estudio.
              </p>
            ))}
        </>
      )}
    </>
  );
}
