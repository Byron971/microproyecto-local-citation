import { Cite, plugins } from '@citation-js/core';
import '@citation-js/plugin-bibtex';
import '@citation-js/plugin-csl';

// La plantilla incluida es «APA Style 7th edition». El parser respeta las
// mayúsculas protegidas con llaves en BibTeX y normaliza títulos en inglés.
const bibtexConfig = plugins.config.get('@bibtex') as { parse: { sentenceCase: string } };
bibtexConfig.parse.sentenceCase = 'english';

export interface ApaReference {
  text: string;
  html: string;
}
export function formatApa7(bibtex: string): ApaReference {
  const citation = new Cite(bibtex);
  if (citation.data.length !== 1 || !citation.data[0].title) {
    throw new Error('La fuente no contiene una referencia bibliográfica única con título.');
  }
  const options = { template: 'apa', lang: 'es-ES' };
  return {
    text: citation
      .format('bibliography', { ...options, format: 'text' })
      .trim()
      .replace(/\s+/g, ' '),
    html: citation.format('bibliography', { ...options, format: 'html' }),
  };
}
