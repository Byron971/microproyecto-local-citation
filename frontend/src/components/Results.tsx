import { Fragment, useEffect, useRef, useState } from 'react';
import { api, type Recommendation } from '../api';
import type { ApaReference } from '../apa';
import { Icon } from './Icon';

const decimal = (n: number) =>
  n.toLocaleString('es', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
export function Results({
  rows,
  label,
  scoreDescription,
}: {
  rows: Recommendation[];
  label: string;
  scoreDescription: string;
}) {
  const [expanded, setExpanded] = useState(() => new Set(rows.slice(0, 1).map((r) => r.paper_id)));
  const [sort, setSort] = useState<{
    key: 'posicion' | 'similitud' | 'similitud_tfidf';
    ascending: boolean;
  }>({ key: 'posicion', ascending: true });
  const [copied, setCopied] = useState('');
  const [copying, setCopying] = useState('');
  const [manualCopy, setManualCopy] = useState<{ id: string; text: string }>();
  const activeCopy = useRef<AbortController | null>(null);
  const references = useRef(new Map<string, ApaReference>());
  useEffect(() => () => activeCopy.current?.abort(), []);
  const hasTfidf = rows.some((r) => r.similitud_tfidf !== undefined);
  const ordered = [...rows].sort(
    (a, b) => ((a[sort.key] ?? -Infinity) - (b[sort.key] ?? -Infinity)) * (sort.ascending ? 1 : -1),
  );
  function toggle(id: string) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  async function copy(id: string) {
    activeCopy.current?.abort();
    const controller = new AbortController();
    activeCopy.current = controller;
    setCopying(id);
    setCopied('Preparando referencia APA 7…');
    setManualCopy(undefined);
    try {
      let reference = references.current.get(id);
      if (!reference) {
        const [metadata, { formatApa7 }] = await Promise.all([
          api.reference(id, controller.signal),
          import('../apa'),
        ]);
        if (controller.signal.aborted) return;
        reference = formatApa7(metadata.bibtex);
        references.current.set(id, reference);
      }
      const { text, html } = reference;
      try {
        if (typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
          await navigator.clipboard.write([
            new ClipboardItem({
              'text/plain': new Blob([text], { type: 'text/plain' }),
              'text/html': new Blob([html], { type: 'text/html' }),
            }),
          ]);
        } else await navigator.clipboard.writeText(text);
        if (!controller.signal.aborted) setCopied('Referencia APA 7 copiada.');
      } catch {
        try {
          await navigator.clipboard.writeText(text);
          if (!controller.signal.aborted) setCopied('Referencia APA 7 copiada en texto plano.');
        } catch {
          if (!controller.signal.aborted) {
            setManualCopy({ id, text });
            setCopied(
              'El navegador no permitió copiar. Selecciona la referencia y usa Ctrl/Cmd+C.',
            );
          }
        }
      }
    } catch {
      if (!controller.signal.aborted)
        setCopied('No se pudo preparar la referencia. Vuelve a intentarlo en unos segundos.');
    } finally {
      if (!controller.signal.aborted) setCopying('');
    }
  }
  function heading(key: typeof sort.key, text: string) {
    return (
      <th
        scope="col"
        aria-sort={sort.key === key ? (sort.ascending ? 'ascending' : 'descending') : 'none'}
      >
        <button
          className="sort"
          title={key === 'similitud' ? scoreDescription : undefined}
          onClick={() =>
            setSort({ key, ascending: sort.key === key ? !sort.ascending : key === 'posicion' })
          }
        >
          {text}
          <span aria-hidden="true"> {sort.key === key ? (sort.ascending ? '↑' : '↓') : '↕'}</span>
        </button>
      </th>
    );
  }
  if (!rows.length)
    return (
      <div className="empty-state">
        <Icon name="search" />
        <h3>No encontramos referencias para este contexto</h3>
        <p>Prueba con un fragmento más largo o más específico, en inglés.</p>
      </div>
    );
  return (
    <>
      <div className="mobile-sort">
        <label htmlFor="result-order">Ordenar referencias</label>
        <select
          id="result-order"
          value={`${sort.key}:${sort.ascending ? 'asc' : 'desc'}`}
          onChange={(e) => {
            const [key, direction] = e.target.value.split(':');
            setSort({ key: key as typeof sort.key, ascending: direction === 'asc' });
          }}
        >
          <option value="posicion:asc">Posición original</option>
          <option value="posicion:desc">Posición inversa</option>
          <option value="similitud:desc">{label}: mayor primero</option>
          <option value="similitud:asc">{label}: menor primero</option>
          {hasTfidf && (
            <>
              <option value="similitud_tfidf:desc">TF-IDF: mayor primero</option>
              <option value="similitud_tfidf:asc">TF-IDF: menor primero</option>
            </>
          )}
        </select>
      </div>
      <div className="table-scroll">
        <table className="results-table">
          <caption className="sr-only">Referencias recomendadas. {scoreDescription}</caption>
          <thead>
            <tr>
              {heading('posicion', '#')}
              <th scope="col">Artículo</th>
              <th scope="col">ID</th>
              {heading('similitud', label)}
              {hasTfidf && heading('similitud_tfidf', 'TF-IDF')}
              <th scope="col">
                <span className="sr-only">Acciones</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((r) => (
              <Fragment key={r.paper_id}>
                <tr>
                  <td className="position">
                    <span className="mobile-label">Posición </span>
                    {String(r.posicion).padStart(2, '0')}
                  </td>
                  <td className="article-cell">
                    <button
                      className="article-title"
                      aria-expanded={expanded.has(r.paper_id)}
                      aria-controls={`abstract-${r.paper_id}`}
                      onClick={() => toggle(r.paper_id)}
                    >
                      <span className={expanded.has(r.paper_id) ? 'chevron open' : 'chevron'}>
                        <Icon name="chevron" size={18} />
                      </span>
                      {r.titulo || '(sin título)'}
                    </button>
                  </td>
                  <td className="paper-id" id={`id-${r.paper_id}`}>
                    {r.paper_id}
                  </td>
                  <td className="score" title={scoreDescription}>
                    <span className="mobile-label">{label} </span>
                    {decimal(r.similitud)}
                  </td>
                  {hasTfidf && (
                    <td className="secondary-score">
                      <span className="mobile-label">TF-IDF </span>
                      {r.similitud_tfidf === undefined ? '—' : decimal(r.similitud_tfidf)}
                    </td>
                  )}
                  <td className="row-actions">
                    <button
                      className="icon-button"
                      aria-label={`Copiar referencia APA 7 de ${r.paper_id}`}
                      title="Copiar referencia APA 7"
                      disabled={copying === r.paper_id}
                      aria-busy={copying === r.paper_id}
                      onClick={() => void copy(r.paper_id)}
                    >
                      <Icon name="copy" size={18} />
                    </button>
                  </td>
                </tr>
                <tr
                  id={`abstract-${r.paper_id}`}
                  hidden={!expanded.has(r.paper_id)}
                  className="abstract-row"
                >
                  <td colSpan={hasTfidf ? 6 : 5}>
                    <div className="abstract-content">
                      <span className="eyebrow">Resumen</span>
                      <p lang="en">{r.resumen || 'Este artículo no tiene resumen.'}</p>
                    </div>
                  </td>
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {manualCopy && (
        <div className="manual-citation">
          <label htmlFor="manual-citation">Referencia APA 7 · {manualCopy.id}</label>
          <textarea
            id="manual-citation"
            readOnly
            rows={5}
            value={manualCopy.text}
            autoFocus
            onFocus={(e) => e.currentTarget.select()}
          />
        </div>
      )}
      <p className="copy-status" role="status">
        {copied}
      </p>
    </>
  );
}
