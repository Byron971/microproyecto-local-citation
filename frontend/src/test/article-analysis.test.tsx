import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ArticleAnalysis } from '../components/ArticleAnalysis';
import { Results } from '../components/Results';
import * as apiModule from '../api';

test('marca la posición seleccionada y envía solo identidad y contexto; descarta resultados al editar', async () => {
  const user = userEvent.setup();
  const classifier = {
    clase: 'Background',
    probabilidad: 0.7,
    ajuste_ph: false,
    probabilidades: Array.from({ length: 9 }, (_, i) => ({
      clase: `Clase ${i}`,
      probabilidad: i ? 0.0375 : 0.7,
    })),
  };
  const request = vi.spyOn(apiModule, 'request').mockResolvedValue({
    articulo: {
      paper_id: 'P14-2008',
      total_fragmentos: 18,
      publicacion: 'https://aclanthology.org/P14-2008/',
      fuente: 'https://example.org',
      licencia: 'CC-BY-NC-4.0',
    },
    top3: [1, 2, 3].map((i) => ({
      chunk_id: `p${i}`,
      texto: `Fragmento recuperado ${i}`,
      similitud_coseno: 0.5,
    })),
    clasificadores: { M: classifier, S: classifier },
    dispositivo: 'cpu',
    tokens_ab: 200,
    revision_scibert: 'abc',
    aviso: 'Experimental',
  });
  render(<ArticleAnalysis paperId="P14-2008" context="Earlier work showed this." />);
  const input = screen.getByLabelText('Contexto de la cita en inglés') as HTMLTextAreaElement;
  input.setSelectionRange(12, 12);
  await user.click(screen.getByRole('button', { name: 'Marcar posición de cita' }));
  expect(input.value).toBe('Earlier work TARGETCIT  showed this.');
  await user.click(screen.getByRole('button', { name: 'Analizar este artículo' }));
  expect(await screen.findByText('Fragmento recuperado 1')).toBeVisible();
  const body = JSON.parse(request.mock.calls[0][1]!.body as string);
  expect(body).toEqual({ paper_id: 'P14-2008', contexto: input.value });
  fireEvent.change(input, { target: { value: 'A changed context' } });
  expect(screen.queryByText('Fragmento recuperado 1')).not.toBeInTheDocument();
});

test('un artículo sin texto no permite iniciar inferencia', async () => {
  vi.spyOn(apiModule, 'request').mockResolvedValue({
    articulos: [{ paper_id: 'P14-9999', disponible: false }],
  });
  render(
    <Results
      rows={[
        {
          paper_id: 'P14-9999',
          titulo: 'Unavailable article',
          resumen: 'Abstract',
          posicion: 1,
          similitud: 0.5,
        },
      ]}
      label="Puntaje"
      scoreDescription="Orden"
      context="Previous work."
    />,
  );
  expect(
    await screen.findByText('Sin texto completo preparado para análisis científico.'),
  ).toBeVisible();
  expect(screen.queryByRole('button', { name: /Analizar cita/ })).not.toBeInTheDocument();
});
