import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { formatApa7 } from '../apa';
import { Results } from '../components/Results';
import { api } from '../api';
import bibtex from './fixtures/acl-P14-1062.bib?raw';

const reference = {
  paper_id: 'P14-1062',
  bibtex,
  source_url: 'https://aclanthology.org/P14-1062/',
};
const row = {
  posicion: 1,
  paper_id: 'P14-1062',
  titulo: 'A Convolutional Neural Network for Modelling Sentences',
  resumen: 'Abstract',
  similitud: 0.9,
};

test('formatea los metadatos oficiales como referencia APA 7 completa', () => {
  const result = formatApa7(bibtex);
  expect(result.text).toMatch(/^Kalchbrenner, N\., Grefenstette, E\., & Blunsom, P\. \(2014\)\./);
  expect(result.text).toContain('A convolutional neural network for modelling sentences.');
  expect(result.text).toContain('En K. Toutanova & H. Wu (Eds.)');
  expect(result.text).toContain('655-665');
  expect(result.text).toContain('https://doi.org/10.3115/v1/P14-1062');
  expect(result.text).not.toContain('Baltimore'); // APA 7 omite la ciudad de la editorial.
  expect(result.html).toContain('<i>');
});
test('no inventa autores ni año si la fuente no los incluye', () => {
  const result = formatApa7(
    '@misc{example,title={A Study of {NLP}},url={https://example.org/paper}}',
  );
  expect(result.text).toContain('A study of NLP.');
  expect(result.text).toMatch(/s\.\s*f\./);
  expect(result.text).not.toContain('Anonymous');
});
test('copiar pega una referencia y no el ID', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('ClipboardItem', undefined);
  const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
  vi.spyOn(api, 'reference').mockResolvedValue(reference);
  render(<Results rows={[row]} label="Puntaje" scoreDescription="Puntaje" />);
  await user.click(screen.getByRole('button', { name: 'Copiar referencia APA 7 de P14-1062' }));
  await screen.findByText('Referencia APA 7 copiada.');
  expect(write).toHaveBeenCalledWith(formatApa7(bibtex).text);
  vi.unstubAllGlobals();
});
test('si el navegador bloquea copiar, ofrece la misma referencia para copia manual', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('ClipboardItem', undefined);
  vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'));
  vi.spyOn(api, 'reference').mockResolvedValue(reference);
  render(<Results rows={[row]} label="Puntaje" scoreDescription="Puntaje" />);
  await user.click(screen.getByRole('button', { name: 'Copiar referencia APA 7 de P14-1062' }));
  expect(await screen.findByLabelText('Referencia APA 7 · P14-1062')).toHaveValue(
    formatApa7(bibtex).text,
  );
  vi.unstubAllGlobals();
});
test('si falla la fuente, no copia un ID ni una referencia incompleta fabricada', async () => {
  const user = userEvent.setup();
  const write = vi.spyOn(navigator.clipboard, 'writeText');
  vi.spyOn(api, 'reference').mockRejectedValue(new Error('offline'));
  render(<Results rows={[row]} label="Puntaje" scoreDescription="Puntaje" />);
  await user.click(screen.getByRole('button', { name: 'Copiar referencia APA 7 de P14-1062' }));
  await screen.findByText(/No se pudo preparar la referencia/);
  expect(write).not.toHaveBeenCalled();
});
