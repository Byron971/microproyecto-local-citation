import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Top3 } from '../pages/Top3';
import { api } from '../api';
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
