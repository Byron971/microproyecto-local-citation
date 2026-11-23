import { useEffect, useRef, useState } from 'react';
import { errorMessage, request } from '../api';

export type PreparedArticle = {
  paper_id: string;
  titulo: string;
  resumen: string;
  publicacion: string;
};

export function ArticlePicker({
  articles,
  version,
  context,
  selected,
  coverage,
  onSelect,
  onRetry,
  onBusyChange,
}: {
  articles: PreparedArticle[];
  version: string;
  context: string;
  selected: string;
  coverage: 'checking' | 'available' | 'missing' | 'error';
  onSelect: (id: string) => void;
  onRetry: () => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(!selected);
  const [suggestions, setSuggestions] = useState<PreparedArticle[]>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const active = useRef<AbortController | null>(null);
  const selectedHeading = useRef<HTMLHeadingElement>(null);
  const focusSelection = useRef(false);
  useEffect(() => {
    if (focusSelection.current && !open) {
      selectedHeading.current?.focus();
      focusSelection.current = false;
    }
  }, [selected, open]);
  const article = articles.find((item) => item.paper_id === selected);
  useEffect(
    () => () => {
      active.current?.abort();
      onBusyChange(false);
    },
    [onBusyChange],
  );
  const normalize = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  const matches = articles.filter((item) =>
    normalize(`${item.titulo} ${item.paper_id}`).includes(normalize(query).trim()),
  );
  const candidates = suggestions ?? matches;
  const pageCount = Math.ceil(candidates.length / 5);
  const currentPage = Math.min(page, Math.max(0, pageCount - 1));
  const visible = candidates.slice(currentPage * 5, currentPage * 5 + 5);

  function cancel() {
    active.current?.abort();
    setBusy(false);
    onBusyChange(false);
  }
  function filter(text: string) {
    cancel();
    setQuery(text);
    setSuggestions(undefined);
    setError('');
    setPage(0);
  }
  async function suggest() {
    if (busy) {
      cancel();
      return;
    }
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    onBusyChange(true);
    setError('');
    try {
      const response = await request<{
        version_contenido: string;
        recomendaciones: { paper_id: string; similitud: number }[];
      }>('/api/analisis-cita-ms/recomendar', {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({ contexto: context, top_k: 5, modelo: 'scibert-articulos-v1' }),
      });
      if (controller.signal.aborted) return;
      if (
        response.version_contenido !== version ||
        !Array.isArray(response.recomendaciones) ||
        response.recomendaciones.length > 5 ||
        new Set(response.recomendaciones.map((r) => r.paper_id)).size !==
          response.recomendaciones.length ||
        response.recomendaciones.some(
          (r) => !articles.some((a) => a.paper_id === r.paper_id) || !Number.isFinite(r.similitud),
        )
      ) {
        throw new Error(
          'Las sugerencias no corresponden al catálogo actual. Busca por título o ID.',
        );
      }
      setSuggestions(
        response.recomendaciones.map((r) => articles.find((a) => a.paper_id === r.paper_id)!),
      );
      setQuery('');
      setPage(0);
    } catch (err) {
      if (!controller.signal.aborted) setError(errorMessage(err));
    } finally {
      if (!controller.signal.aborted) {
        setBusy(false);
        onBusyChange(false);
      }
    }
  }
  function choose(id: string) {
    cancel();
    focusSelection.current = true;
    onSelect(id);
    setOpen(false);
  }
  return (
    <div className="article-picker">
      <p id="article-help" className="field-help">
        Elige el artículo al que corresponde tu cita. Los tres fragmentos se buscarán dentro de él.
      </p>
      {article && (
        <section className="chosen-article" aria-label="Artículo seleccionado">
          <div className="chosen-article-heading">
            <span className="selection-label">✓ Artículo seleccionado</span>
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={() => setOpen(!open)}
            >
              {open ? 'Cerrar búsqueda' : 'Cambiar artículo'}
            </button>
          </div>
          <h3 ref={selectedHeading} tabIndex={-1}>
            {article.titulo}
          </h3>
          <p className="article-citation">
            <span>{article.paper_id}</span>
            <a href={article.publicacion} target="_blank" rel="noreferrer">
              Abrir publicación
            </a>
          </p>
          <div className="article-coverage" aria-live="polite">
            {coverage === 'checking' && <p role="status">Consultando texto preparado…</p>}
            {coverage === 'available' && <p role="status">Texto preparado: disponible.</p>}
            {coverage === 'missing' && (
              <p role="status">
                Este artículo no tiene texto preparado en el servicio. Conservamos tu contexto;
                selecciona otro artículo.
              </p>
            )}
            {coverage === 'error' && (
              <>
                <p role="status">
                  No se pudo consultar la disponibilidad. Esto no significa que falte el texto del
                  artículo.
                </p>
                <button type="button" className="text-button" onClick={onRetry}>
                  Reintentar disponibilidad
                </button>
              </>
            )}
          </div>
        </section>
      )}
      {(open || !article) && (
        <div className="article-discovery">
          <label htmlFor="article-filter">Buscar por título o ID</label>
          <input
            id="article-filter"
            type="search"
            value={query}
            placeholder="Por ejemplo: translation o W05-0821"
            onChange={(e) => filter(e.target.value)}
            aria-describedby="article-search-count"
          />
          <div className="article-suggest-action">
            <span>¿No tienes el título a mano?</span>
            <button type="button" className="secondary-button" onClick={() => void suggest()}>
              {busy ? 'Cancelar búsqueda' : 'Sugerir según mi contexto'}
            </button>
          </div>
          {busy && (
            <p role="status" className="field-help">
              Buscando artículos relacionados con SciBERT…
            </p>
          )}
          {error && (
            <p role="alert" className="error-message">
              {error} Puedes seguir buscando por título o ID.
            </p>
          )}
          <div className="article-list-heading">
            <h3>
              {suggestions
                ? 'Sugeridos según tu contexto'
                : query
                  ? 'Resultados de búsqueda'
                  : 'Artículos del catálogo'}
            </h3>
            <span id="article-search-count" aria-live="polite">
              {query ? `${candidates.length} coincidencias` : `${candidates.length} artículos`}
            </span>
          </div>
          {suggestions && (
            <p className="field-help">
              Son candidatos relacionados, no una identificación de la referencia. Confirma el
              título y la fuente.
            </p>
          )}
          {candidates.length === 0 && (
            <p className="field-help">
              No hay artículos con esa búsqueda. Prueba otro título o ID, o pide sugerencias con tu
              contexto.
            </p>
          )}
          <ul className="article-options" aria-label="Artículos encontrados">
            {visible.map((item) => (
              <li
                key={item.paper_id}
                className={item.paper_id === selected ? 'article-option-selected' : ''}
              >
                <button
                  type="button"
                  className="article-option"
                  disabled={busy}
                  aria-label={`Seleccionar artículo: ${item.titulo} · ${item.paper_id}`}
                  aria-pressed={item.paper_id === selected}
                  onClick={() => choose(item.paper_id)}
                >
                  <strong>{item.titulo}</strong>
                  <span className="article-id">{item.paper_id}</span>
                  <span className="article-abstract" lang="en">
                    {item.resumen}
                  </span>
                  <span className="article-select-label" aria-hidden="true">
                    Seleccionar artículo →
                  </span>
                </button>
                <a
                  className="article-source"
                  href={item.publicacion}
                  target="_blank"
                  rel="noreferrer"
                >
                  Ver publicación<span className="sr-only">: {item.titulo}</span>
                </a>
              </li>
            ))}
          </ul>
          {pageCount > 1 && (
            <nav className="article-pagination" aria-label="Páginas de artículos">
              <button
                type="button"
                className="text-button"
                disabled={currentPage === 0 || busy}
                onClick={() => setPage(currentPage - 1)}
              >
                Anterior
              </button>
              <span>
                Página {currentPage + 1} de {pageCount}
              </span>
              <button
                type="button"
                className="text-button"
                disabled={currentPage + 1 === pageCount || busy}
                onClick={() => setPage(currentPage + 1)}
              >
                Siguiente
              </button>
            </nav>
          )}
        </div>
      )}
    </div>
  );
}
