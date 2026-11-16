import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CitationFunction } from '../pages/CitationFunction';
import { api, ApiError } from '../api';

afterEach(() => vi.restoreAllMocks());

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Contexto de cita (en inglés)'),
    'We compare prior work TARGETCIT with our proposal.');
  await user.type(screen.getByLabelText('Título real del artículo citado'), 'Graph Science');
  await user.type(screen.getByLabelText('Abstract real del artículo citado'),
    'A study of representations and comparisons.');
}

test('muestra nueve scores de A4 como PROVISIONALES, nunca como Gold', async () => {
  const fn = vi.spyOn(api, 'classifyCitation').mockResolvedValue({
    modelo: 'scibert_A_42',
    encoder: 'scibert', entrada: 'A', clase: 'Comparison', indice_clase: 3,
    puntuaciones_softmax: [
      'Background', 'Gap', 'Basis', 'Comparison', 'Application',
      'Improvement / Modification', 'Evidence',
      'Identification of the Originator', 'Further Reading',
    ].map((categoria, i) => ({ categoria, score: i === 3 ? 0.65 : 0.04375 })),
    latencia_modelo_ms: 4.2,
    training_labels: 'Haiku',
    validacion: 'provisional_no_gold_humano',
    advertencia: 'No calibradas.',
  });
  const user = userEvent.setup();
  render(<CitationFunction />);
  await fill(user);
  await user.click(screen.getByRole('button', { name: 'Clasificar función de cita' }));
  expect(await screen.findByRole('heading', { name: 'Función estimada: Comparison' })).toBeVisible();
  expect(screen.getByText(/no están validados sobre Test Gold humano/)).toBeVisible();
  expect(screen.getByText(/No interpretarlos como probabilidades de acierto/)).toBeVisible();
  expect(screen.getAllByRole('listitem')).toHaveLength(9);
  expect(fn).toHaveBeenCalledWith(
    'We compare prior work TARGETCIT with our proposal.',
    'Graph Science', 'A study of representations and comparisons.', expect.any(AbortSignal),
  );
});

test('sin checkpoint informa explícitamente que A4 no está disponible', async () => {
  vi.spyOn(api, 'classifyCitation').mockRejectedValue(new ApiError('sin pesos', 503));
  const user = userEvent.setup();
  render(<CitationFunction />);
  await fill(user);
  await user.click(screen.getByRole('button', { name: 'Clasificar función de cita' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'no está instalado con un checkpoint verificado',
  );
});

test('sin TARGETCIT no consulta el backend', async () => {
  const fn = vi.spyOn(api, 'classifyCitation');
  const user = userEvent.setup();
  render(<CitationFunction />);
  await user.type(screen.getByLabelText('Contexto de cita (en inglés)'), 'Without a marker.');
  await user.type(screen.getByLabelText('Título real del artículo citado'), 'Paper');
  await user.type(screen.getByLabelText('Abstract real del artículo citado'), 'Abstract');
  await user.click(screen.getByRole('button', { name: 'Clasificar función de cita' }));
  expect(screen.getByRole('alert')).toHaveTextContent('un único TARGETCIT');
  expect(fn).not.toHaveBeenCalled();
});


test('SPECTER-A usa su endpoint y rechaza sustitución silenciosa por SciBERT', async () => {
  const scibert = vi.spyOn(api, 'classifyCitation');
  const specter = vi.spyOn(api, 'classifyCitationSpecterA').mockResolvedValue({
    modelo: 'specter_A_42', encoder: 'specter', entrada: 'A',
    clase: 'Comparison', indice_clase: 3,
    puntuaciones_softmax: [
      'Background', 'Gap', 'Basis', 'Comparison', 'Application',
      'Improvement / Modification', 'Evidence',
      'Identification of the Originator', 'Further Reading',
    ].map((categoria, i) => ({ categoria, score: i === 3 ? 0.68 : 0.04 })),
    latencia_modelo_ms: 6.1, training_labels: 'Haiku',
    validacion: 'provisional_no_gold_humano', advertencia: 'No Gold',
  });
  const user = userEvent.setup();
  render(<CitationFunction />);
  await user.selectOptions(screen.getByLabelText('Encoder de clasificación A'), 'specter');
  await fill(user);
  await user.click(screen.getByRole('button', {name: 'Clasificar función de cita'}));
  expect(await screen.findByText('specter_A_42 · Entrada A')).toBeVisible();
  expect(specter).toHaveBeenCalled();
  expect(scibert).not.toHaveBeenCalled();
});
