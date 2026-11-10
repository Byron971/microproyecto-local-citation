import { useEffect, useRef } from 'react';
import type { ExamplesCatalog } from '../api';

export function ExampleDialog({
  examples,
  selected,
  onSelect,
  onClose,
}: {
  examples: ExamplesCatalog['ejemplos'];
  selected?: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current!;
    if (!element.open) element.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="example-dialog"
      aria-labelledby="examples-title"
      aria-describedby="examples-description"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const bounds = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
          )
            onClose();
        }
      }}
    >
      <div className="example-dialog-header">
        <div>
          <h2 id="examples-title">Elige un ejemplo</h2>
          <p id="examples-description">Selecciona un fragmento real para probar el recomendador.</p>
        </div>
        <button
          type="button"
          className="example-dialog-close"
          aria-label="Cerrar ejemplos"
          onClick={onClose}
        >
          ×
        </button>
      </div>
      <ul className="example-list">
        {examples.map((item) => (
          <li key={item.context_id}>
            <button
              type="button"
              className="example-card"
              onClick={() => onSelect(item.context_id)}
            >
              <span className="example-card-heading">
                <strong>{item.titulo_correcto}</strong>
                {selected === item.context_id && <span className="example-selected">En uso</span>}
              </span>
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
