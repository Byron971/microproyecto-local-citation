import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Top3 } from '../pages/Top3';
import { api, ApiError } from '../api';

afterEach(() => vi.restoreAllMocks());
test('recupera fragmentos y no presenta una clasificación inventada', async () => {
  vi.spyOn(api, 'top3').mockResolvedValue({
    cited_id: 'ejemplo-sintetico',
    total_fragmentos_analizados: 3,
    fragmentos: [{ chunk_id: 'p1', posicion: 1, texto: 'Graph evidence', puntaje_bm25: 1 }],
    clasificacion: { estado: 'no_ejecutada' },
  });
  const user = userEvent.setup();
  render(<Top3 />);
  await user.click(screen.getByRole('button', { name: 'Usar ejemplo sintético' }));
  await user.click(screen.getByRole('button', { name: 'Buscar evidencia Top-3' }));
  expect(await screen.findByText('Graph evidence')).toBeVisible();
  expect(screen.getByText('Clasificación aún no disponible')).toBeVisible();
});

test('recupera un caso TRAIN real mediante los endpoints de corpus, sin reclamar Gold', async () => {
  vi.spyOn(api, 'top3CorpusExamples').mockResolvedValue({
    total: 1,
    ejemplos: [{ context_id: 'P15-1001_P14-1001_0', cited_id: 'P14-1001',
      cited_title: 'Neural Graph Model', total_chunks: 3 }],
  });
  const getCase = vi.spyOn(api, 'top3Corpus').mockResolvedValue({
    context_id: 'P15-1001_P14-1001_0',
    contexto: 'We applied graph models TARGETCIT.',
    cited_id: 'P14-1001',
    cited_title: 'Neural Graph Model',
    split: 'train',
    fuente: 'ACL-200 + ACL OCL local',
    metodo: 'BM25_lexico_baseline',
    aviso: 'Muestra de desarrollo TRAIN, no Gold.',
    sha256_ocl_citado: 'a'.repeat(64),
    total_fragmentos_analizados: 3,
    fragmentos: [
      { chunk_id: 'p00001-p00001', posicion: 1, texto: 'Graph methods use nodes.',
        seccion: 'Methods', puntaje_bm25: 2.5 },
    ],
    clasificacion: { estado: 'no_ejecutada' },
  });
  const user = userEvent.setup();
  render(<Top3 />);
  await user.click(screen.getByRole('button', { name: 'Cargar casos reales de desarrollo' }));
  expect(await screen.findByRole('combobox', { name: 'Caso del corpus' })).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Ejecutar Top-3 de desarrollo' }));
  expect(await screen.findByText('Graph methods use nodes.')).toBeVisible();
  expect(getCase).toHaveBeenCalledWith('P15-1001_P14-1001_0', expect.any(AbortSignal));
  expect(screen.getByText(/subconjunto TRAIN · BM25/)).toBeVisible();
  expect(screen.getByText('Clasificación aún no disponible')).toBeVisible();
});

test('sin artefacto local de TRAIN informa bloqueo y conserva modo manual', async () => {
  vi.spyOn(api, 'top3CorpusExamples').mockRejectedValue(
    new ApiError('El artefacto no existe.', 503),
  );
  const user = userEvent.setup();
  render(<Top3 />);
  await user.click(screen.getByRole('button', { name: 'Cargar casos reales de desarrollo' }));
  expect(await screen.findByRole('status')).toHaveTextContent(
    'no tiene instalado el artefacto de desarrollo',
  );
  expect(screen.getByRole('button', { name: 'Usar ejemplo sintético' })).toBeEnabled();
});
