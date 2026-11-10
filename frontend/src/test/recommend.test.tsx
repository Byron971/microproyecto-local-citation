import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Recommend } from '../pages/Recommend';
import { api, ApiError } from '../api';
import { Results } from '../components/Results';

const model = {
  id: 'test-model',
  nombre: 'Modelo integrado',
  descripcion: 'Modelo real',
  disponible: true,
  motivo: null,
  puntaje: { etiqueta: 'Puntaje de prueba', descripcion: 'No es una garantía' },
  devuelve_tfidf: true,
};
const catalog = { predeterminado: model.id, modelos: [model] };
const row = {
  posicion: 1,
  paper_id: 'P01',
  titulo: 'Graph representations',
  resumen: 'A complete abstract.',
  similitud: 0.8,
  similitud_tfidf: 0.3,
};
const response = { consulta: 'graph networks', modelo: model.id, total: 1, recomendaciones: [row] };
beforeEach(() => {
  localStorage.clear();
  vi.spyOn(api, 'models').mockResolvedValue(catalog);
  vi.spyOn(api, 'examples').mockResolvedValue({
    total: 2,
    particion: 'val',
    ejemplos: [
      {
        context_id: 'example-1',
        texto: 'graph networks',
        cita_correcta: 'P01',
        titulo_correcto: row.titulo,
      },
      {
        context_id: 'example-2',
        texto: 'Machine translation evaluation',
        cita_correcta: 'P02',
        titulo_correcto: 'Translation quality',
      },
    ],
  });
  vi.spyOn(api, 'recommend').mockResolvedValue(response);
});

test('no muestra resultados iniciales ni envía un contexto vacío', async () => {
  const user = userEvent.setup();
  render(<Recommend />);
  expect(
    screen.queryByRole('heading', { name: /Referencias recomendadas/ }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Recomendar' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Escribe o pega');
  expect(api.recommend).not.toHaveBeenCalled();
});
test('envía el modelo elegido y muestra referencias sin etiquetas de evaluación', async () => {
  const user = userEvent.setup();
  render(<Recommend />);
  await screen.findByText(model.nombre);
  await screen.findByRole('button', { name: 'Usar un ejemplo' });
  await user.click(screen.getByRole('button', { name: 'Usar un ejemplo' }));
  await user.click(await screen.findByRole('button', { name: /Graph representations/ }));
  await user.click(screen.getByRole('button', { name: 'Recomendar' }));
  expect(await screen.findByText(row.titulo)).toBeVisible();
  expect(screen.queryByText(/cita correcta/i)).not.toBeInTheDocument();
  expect(api.recommend).toHaveBeenCalledWith(
    'graph networks',
    10,
    model.id,
    expect.any(AbortSignal),
  );
  await user.type(screen.getByLabelText(/Contexto en inglés/), ' edited');
  expect(screen.queryByText('Cita correcta')).not.toBeInTheDocument();
  expect(screen.getByText(/Resultados de la consulta anterior/)).toBeVisible();
});
test('una falla del catálogo permite consultar el predeterminado', async () => {
  vi.mocked(api.models).mockRejectedValue(new Error('Offline'));
  const user = userEvent.setup();
  render(<Recommend />);
  await screen.findByText(/No se pudo cargar la lista/);
  await user.type(screen.getByLabelText(/Contexto en inglés/), 'graph networks');
  await user.click(screen.getByRole('button', { name: 'Recomendar' }));
  await screen.findByText(row.titulo);
  expect(api.recommend).toHaveBeenCalledWith(
    'graph networks',
    10,
    undefined,
    expect.any(AbortSignal),
  );
});
test('muestra 503 y permite reintentar la consulta', async () => {
  vi.mocked(api.recommend).mockRejectedValueOnce(new ApiError('Not ready', 503));
  const user = userEvent.setup();
  render(<Recommend />);
  await screen.findByText(model.nombre);
  await user.type(screen.getByLabelText(/Contexto en inglés/), 'graph networks');
  await user.click(screen.getByRole('button', { name: 'Recomendar' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('no está disponible');
  await user.click(screen.getByRole('button', { name: 'Reintentar' }));
  expect(await screen.findByText(row.titulo)).toBeVisible();
});
test('descarta una respuesta antigua aunque el transporte ignore abort', async () => {
  let first: (value: typeof response) => void = () => {};
  let second: (value: typeof response) => void = () => {};
  vi.mocked(api.recommend)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          first = resolve;
        }),
    )
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          second = resolve;
        }),
    );
  render(<Recommend />);
  await screen.findByText(model.nombre);
  const input = screen.getByLabelText(/Contexto en inglés/);
  fireEvent.change(input, { target: { value: 'first' } });
  fireEvent.submit(screen.getByRole('button', { name: 'Recomendar' }).closest('form')!);
  fireEvent.change(input, { target: { value: 'second' } });
  fireEvent.submit(screen.getByRole('button', { name: 'Buscando…' }).closest('form')!);
  second({ ...response, recomendaciones: [{ ...row, titulo: 'Newest response' }] });
  await screen.findByText('Newest response');
  first({ ...response, recomendaciones: [{ ...row, titulo: 'Stale response' }] });
  await waitFor(() => expect(screen.queryByText('Stale response')).not.toBeInTheDocument());
});
test('ordena puntajes conservando la posición original y expande resúmenes', async () => {
  const user = userEvent.setup();
  render(
    <Results
      rows={[row, { ...row, posicion: 2, paper_id: 'P02', titulo: 'Second paper', similitud: 0.9 }]}
      label="Puntaje"
      scoreDescription="Descripción"
    />,
  );
  expect(screen.getAllByText('A complete abstract.')[0]).toBeVisible();
  await user.click(screen.getByRole('button', { name: /Puntaje/ }));
  const rows = screen.getAllByRole('row');
  expect(rows[1]).toHaveTextContent('Second paper');
  expect(rows[1]).toHaveTextContent('02');
  await user.click(screen.getByRole('button', { name: 'Second paper' }));
  expect(
    screen.getAllByText('A complete abstract.').filter((e) => e.closest('[hidden]') === null),
  ).toHaveLength(2);
});

test('permite elegir distintos contextos y consultar la ayuda del modelo', async () => {
  const user = userEvent.setup();
  render(<Recommend />);
  await screen.findByRole('button', { name: 'Usar un ejemplo' });
  await user.click(screen.getByRole('button', { name: 'Usar un ejemplo' }));
  await user.click(await screen.findByRole('button', { name: /Graph representations/ }));
  expect(screen.getByLabelText('Contexto en inglés')).toHaveValue('graph networks');
  await user.click(screen.getByRole('button', { name: 'Usar un ejemplo' }));
  await user.click(await screen.findByRole('button', { name: /Translation quality/ }));
  expect(screen.getByLabelText('Contexto en inglés')).toHaveValue('Machine translation evaluation');
  await user.click(screen.getByRole('button', { name: 'Qué hace este modelo' }));
  expect(screen.getByRole('note')).toHaveTextContent(model.descripcion);
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('note')).not.toBeInTheDocument();
});
