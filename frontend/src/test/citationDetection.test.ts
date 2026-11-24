import { describe, expect, test } from 'vitest';
import { detectCitations, markCitation } from '../citationDetection';

const labels = (text: string) => detectCitations(text).map((c) => c.label);

describe('detectCitations', () => {
  test('referencia numérica entre corchetes', () => {
    expect(labels('The approach described in [1] improves SMT.')).toEqual(['[1]']);
  });

  test('autor-año entre paréntesis o corchetes', () => {
    expect(labels('Earlier work (Smith, 2020) and [Lee et al., 2019a] showed it.')).toEqual([
      '(Smith, 2020)',
      '[Lee et al., 2019a]',
    ]);
  });

  test('cita narrativa', () => {
    expect(labels('Smith et al. (2020) and Lee and Kim (2018) proposed it.')).toEqual([
      'Smith et al. (2020)',
      'Lee and Kim (2018)',
    ]);
  });

  test('separa grupos con varias referencias', () => {
    const text = 'Prior work (Smith, 2020; Lee, 2019) and [2, 3].';
    expect(labels(text)).toEqual(['Smith, 2020', 'Lee, 2019', '2', '3']);
    const [first] = detectCitations(text);
    expect(markCitation(text, first)).toBe('Prior work (TARGETCIT; Lee, 2019) and [2, 3].');
  });

  test('una referencia aislada se reemplaza completa', () => {
    const text = 'We use the method described in [1] here.';
    expect(markCitation(text, detectCitations(text)[0])).toBe(
      'We use the method described in TARGETCIT here.',
    );
  });

  test('ignora paréntesis sin referencias y marcas existentes', () => {
    expect(labels('Accuracy improves (see Table 2) by 3 points (p < 0.05).')).toEqual([]);
    expect(labels('Prior work TARGETCIT and OTHERCIT.')).toEqual([]);
  });
});
