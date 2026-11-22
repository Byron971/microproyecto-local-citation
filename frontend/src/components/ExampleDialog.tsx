import { useEffect, useRef, useState } from 'react';
import type { ExamplesCatalog } from '../api';

export function ExampleDialog({
  examples,
  selected,
  onSelect,
  onClose,
  searchable = false,
  description = 'Selecciona un fragmento real para probar el recomendador.',
}: {
  examples: (ExamplesCatalog['ejemplos'][number] & { detalle?: string })[];
  searchable?: boolean;
  description?: string;
  selected?: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const normalize = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
  const filtered = examples.filter((item) =>
    terms.every((term) =>
      normalize(
        `${item.titulo_correcto} ${item.texto} ${item.context_id} ${item.cita_correcta} ${item.detalle || ''}`,
      ).includes(term),
    ),
  );
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current!;
    if (!element.open) element.showModal();
    if (searchable) element.querySelector<HTMLInputElement>('input[type="search"]')?.focus();
  }, [searchable]);
  function close() {
    dialog.current?.close();
    onClose();
  }
  return (
    <dialog
      ref={dialog}
      className="example-dialog"
      aria-labelledby="examples-title"
      aria-describedby="examples-description"
      onClose={onClose}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          close();
        }
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const bounds = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
          )
            close();
        }
      }}
    >
      <div className="example-dialog-header">
        <div>
          <h2 id="examples-title">Elige un ejemplo</h2>
          <p id="examples-description">{description}</p>
        </div>
        <button
          type="button"
          className="example-dialog-close"
          aria-label="Cerrar ejemplos"
          onClick={close}
        >
          ×
        </button>
      </div>
      {searchable && (
        <div className="example-search">
          <label htmlFor="example-search">Buscar ejemplos</label>
          <input
            id="example-search"
            type="search"
            value={query}
            placeholder="Texto de la cita, título o ID"
            onChange={(event) => setQuery(event.target.value)}
          />
          <p role="status">
            {filtered.length} de {examples.length} ejemplos
          </p>
        </div>
      )}
      {filtered.length === 0 && (
        <p className="example-empty">No hay ejemplos con esa búsqueda. Prueba otras palabras.</p>
      )}
      <ul className="example-list">
        {filtered.map((item) => (
          <li key={item.context_id}>
            <button
              type="button"
              className="example-card"
              onClick={() => {
                dialog.current?.close();
                onSelect(item.context_id);
              }}
            >
              <span className="example-card-heading">
                <strong>{item.titulo_correcto}</strong>
                {selected === item.context_id && <span className="example-selected">En uso</span>}
              </span>
              {item.detalle && <span className="example-metadata">{item.detalle}</span>}
              <span className="example-preview" lang="en">
                {item.texto}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </dialog>
  );
}
