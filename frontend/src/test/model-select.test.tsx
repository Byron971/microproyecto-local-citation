import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { ModelSelect } from '../components/ModelSelect';

test('permite elegir con teclado, indica opciones no disponibles y cierra con Escape', async () => {
  const user = userEvent.setup();
  const change = vi.fn();
  render(
    <>
      <label id="model-label" htmlFor="model">
        Modelo
      </label>
      <ModelSelect
        value="first"
        disabled={false}
        placeholder="Selecciona un modelo"
        onChange={change}
        options={[
          { id: 'first', nombre: 'Modelo actual', disponible: true },
          { id: 'blocked', nombre: 'Modelo futuro', disponible: false },
          { id: 'second', nombre: 'Otro modelo', disponible: true },
        ]}
      />
    </>,
  );
  const trigger = screen.getByRole('combobox');
  await user.click(trigger);
  expect(screen.getByRole('option', { name: 'Modelo actual' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await user.keyboard('{ArrowDown}{Enter}');
  expect(change).not.toHaveBeenCalled();
  expect(screen.getByRole('listbox')).toBeVisible();
  await user.keyboard('{ArrowDown}{Enter}');
  expect(change).toHaveBeenCalledWith('second');
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  await user.keyboard('{ArrowDown}{Escape}');
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
});
