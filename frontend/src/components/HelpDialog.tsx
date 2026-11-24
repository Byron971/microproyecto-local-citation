import { useEffect, useId, useRef } from 'react';

export function HelpDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const id = useId();
  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    title.current?.focus();
    return () => element.close();
  }, []);
  function close() {
    dialog.current?.close();
    onClose();
  }
  return (
    <dialog
      ref={dialog}
      className="example-dialog help-dialog"
      aria-labelledby={id}
      onClose={(event) => {
        if (!event.currentTarget.open) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== 'Tab') return;
        const controls = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            'button, a[href], input, select, textarea, [tabindex="0"]',
          ),
        );
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first || document.activeElement === title.current)
        ) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const rect = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < rect.left ||
          event.clientX > rect.right ||
          event.clientY < rect.top ||
          event.clientY > rect.bottom
        )
          close();
      }}
    >
      <div className="example-dialog-header">
        <div>
          <h2 id={id} ref={title} tabIndex={-1}>
            Cómo analizar una cita
          </h2>
        </div>
        <button
          type="button"
          className="example-dialog-close"
          aria-label="Cerrar ayuda"
          onClick={close}
        >
          ×
        </button>
      </div>
      <div className="help-dialog-content">
        <ol className="help-workflow">
          <li>
            <h3>Contexto</h3>
            <p>Pega el párrafo en inglés que contiene la cita o elige «Explorar ejemplos».</p>
          </li>
          <li>
            <h3>Artículo</h3>
            <p>
              Busca por título o ID, o revisa las sugerencias según tu contexto. Confirma el
              artículo citado y que tenga texto disponible.
            </p>
          </li>
          <li>
            <h3>Clasificador</h3>
            <p>
              Elige el modelo y pulsa «Ver resultados». El comercial requiere tu consentimiento para
              enviar el contexto, el título y el resumen a OpenAI.
            </p>
          </li>
          <li>
            <h3>Resultados</h3>
            <p>
              Espera el cálculo y revisa los tres fragmentos del artículo y la función predicha.
              Consulta «Detalles del análisis» o «Funciones de cita» para interpretarlos.
            </p>
          </li>
        </ol>
        <div className="help-context-note">
          <h3>¿Cómo se marca la cita?</h3>
          <p>
            Si hay una sola referencia, se identifica automáticamente; si hay varias, elige una. Si
            no se detecta, selecciónala en el texto y pulsa «Usar selección».
          </p>
          <p>
            En los ejemplos, <code>TARGETCIT</code> identifica la cita elegida y{' '}
            <code>OTHERCIT</code> representa otras referencias.
          </p>
        </div>
        <p className="help-interpretation">
          Los fragmentos son candidatos relacionados. La función es una predicción; las puntuaciones
          no indican porcentajes de acierto.
        </p>
      </div>
    </dialog>
  );
}
