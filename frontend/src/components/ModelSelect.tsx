import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon';

type Option = { id: string; nombre: string; disponible: boolean };
export function ModelSelect({
  options,
  value,
  disabled,
  placeholder,
  onChange,
}: {
  options: Option[];
  value: string;
  disabled: boolean;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const selected = options.find((option) => option.id === value);
  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  function show() {
    setActive(
      Math.max(
        0,
        options.findIndex((option) => option.id === value),
      ),
    );
    setOpen(true);
  }
  function choose(option: Option) {
    if (!option.disponible) return;
    onChange(option.id);
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <div
      className="model-select"
      ref={root}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false);
      }}
    >
      <button
        id="model"
        ref={trigger}
        className="model-trigger"
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="model-options"
        aria-labelledby="model-label model-value"
        aria-activedescendant={open && options[active] ? `model-option-${active}` : undefined}
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={(event) => {
          if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
            event.preventDefault();
            if (!open) {
              show();
              return;
            }
            setActive((index) =>
              event.key === 'Home'
                ? 0
                : event.key === 'End'
                  ? options.length - 1
                  : (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) %
                    options.length,
            );
          } else if (event.key === 'Escape') {
            event.preventDefault();
            setOpen(false);
          } else if ((event.key === 'Enter' || event.key === ' ') && open) {
            event.preventDefault();
            if (options[active]) choose(options[active]);
          } else if (event.key.length === 1 && event.key !== ' ') {
            const index = options.findIndex((option) =>
              option.nombre.toLocaleLowerCase().startsWith(event.key.toLocaleLowerCase()),
            );
            if (index >= 0) {
              setOpen(true);
              setActive(index);
            }
          }
        }}
      >
        <span id="model-value">{selected?.nombre || placeholder}</span>
        <Icon name="chevron" size={18} />
      </button>
      {open && (
        <ul
          id="model-options"
          className="model-options"
          role="listbox"
          aria-labelledby="model-label"
        >
          {options.map((option, index) => (
            <li
              key={option.id}
              id={`model-option-${index}`}
              role="option"
              aria-selected={option.id === value}
              aria-disabled={!option.disponible}
              className={active === index ? 'is-active' : ''}
              onPointerMove={() => setActive(index)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(option)}
            >
              <span>
                {option.nombre}
                {!option.disponible && <small>No disponible</small>}
              </span>
              {option.id === value && (
                <span className="model-check" aria-hidden="true">
                  ✓
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
