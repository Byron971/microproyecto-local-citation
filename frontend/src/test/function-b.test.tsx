import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CitationFunctionB } from '../pages/CitationFunctionB';
import { api, ApiError, type FunctionBResponse } from '../api';

afterEach(() => vi.restoreAllMocks());

const response: FunctionBResponse = {
  context_id: null,
  cited_id: 'P14-1001',
  recuperacion: {
    metodo: 'scibert_base_mean_pooling_cosine', modelo: 'SciBERT_base_mean_pooling',
    revision: 'a'.repeat(40),
    fragmentos: [
      { posicion: 1, chunk_id: 'p1', texto: 'Graph models use citations.',
        seccion: 'Methods', similitud_coseno: 0.9 },
      { posicion: 2, chunk_id: 'p2', texto: 'The method compares graph data.',
        seccion: 'Results', similitud_coseno: 0.8 },
      { posicion: 3, chunk_id: 'p3', texto: 'Paper describes datasets.',
        seccion: 'Introduction', similitud_coseno: 0.7 },
    ],
  },
  clasificacion: {
    modelo: 'scibert_B_42', encoder: 'scibert', entrada: 'B',
    clase: 'Comparison', indice_clase: 3, latencia_modelo_ms: 4.5,
    training_labels: 'Haiku', validacion: 'provisional_no_gold_humano',
    puntuaciones_softmax: [
      'Background', 'Gap', 'Basis', 'Comparison', 'Application',
      'Improvement / Modification', 'Evidence',
      'Identification of the Originator', 'Further Reading',
    ].map((categoria, i) => ({categoria, score: i === 3 ? .6 : .05})),
    advertencia: 'Provisional',
  },
  split: null, gold_certificado: false, aviso: 'Haiku provisional',
};

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Contexto con TARGETCIT'),
    'We compare graph methods TARGETCIT and applications.');
  await user.type(screen.getByLabelText('ID del artículo citado'), 'P14-1001');
  await user.type(screen.getByLabelText('Párrafos del citado (al menos tres)'),
    'Graph method one.{enter}{enter}Graph method two.{enter}{enter}Graph method three.');
}

test('B muestra tres fragmentos SciBERT y nueve scores Haiku con disclaimer Gold', async () => {
  const client = vi.spyOn(api, 'classifyCitationB').mockResolvedValue(response);
  const user = userEvent.setup();
  render(<CitationFunctionB />);
  await fill(user);
  await user.click(screen.getByRole('button', { name: 'Recuperar Top-3 y clasificar B' }));
  expect(await screen.findByRole('heading', { name: 'Función estimada: Comparison' })).toBeVisible();
  expect(screen.getByText('Graph models use citations.')).toBeVisible();
  expect(screen.getByText(/Resultado provisional Haiku/)).toBeVisible();
  expect(screen.getByText('Further Reading: 0.050')).toBeVisible();
  expect(client).toHaveBeenCalledWith(expect.any(String), 'P14-1001',
    expect.any(Array), expect.any(AbortSignal));
});

test('B falla explícitamente cuando faltan SciBERT o checkpoint, sin BM25', async () => {
  const client = vi.spyOn(api, 'classifyCitationB').mockRejectedValue(
    new ApiError('checkpoint ausente', 503),
  );
  const fallback = vi.spyOn(api, 'top3');
  const user = userEvent.setup();
  render(<CitationFunctionB />);
  await fill(user);
  await user.click(screen.getByRole('button', { name: 'Recuperar Top-3 y clasificar B' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('No hay sustitución por BM25');
  expect(client).toHaveBeenCalled();
  expect(fallback).not.toHaveBeenCalled();
});

test('B no llama al modelo con solo dos párrafos', async () => {
  const client = vi.spyOn(api, 'classifyCitationB');
  const user = userEvent.setup();
  render(<CitationFunctionB />);
  await user.type(screen.getByLabelText('Contexto con TARGETCIT'), 'Graph TARGETCIT');
  await user.type(screen.getByLabelText('ID del artículo citado'), 'P14-1001');
  await user.type(screen.getByLabelText('Párrafos del citado (al menos tres)'),
    'First paragraph.{enter}{enter}Second paragraph.');
  await user.click(screen.getByRole('button', { name: 'Recuperar Top-3 y clasificar B' }));
  expect(screen.getByRole('alert')).toHaveTextContent('entre 3 y 100 párrafos');
  expect(client).not.toHaveBeenCalled();
});

test('B autentica solo casos disponibles de TRAIN de la API', async () => {
  vi.spyOn(api, 'top3CorpusExamples').mockResolvedValue({
    total: 1, ejemplos: [{
      context_id: 'ctx1', cited_id: 'P14-1001',
      cited_title: 'Graphs', total_chunks: 3,
    }],
  });
  vi.spyOn(api, 'classifyCitationBCorpus').mockResolvedValue({
    ...response, context_id: 'ctx1', split: 'train',
  });
  const user = userEvent.setup();
  render(<CitationFunctionB />);
  await user.click(screen.getByRole('button', { name: 'Cargar ejemplos de desarrollo' }));
  expect(await screen.findByLabelText('Caso de desarrollo')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Clasificar cita B de TRAIN' }));
  expect(await screen.findByText('Graph models use citations.')).toBeVisible();
});
