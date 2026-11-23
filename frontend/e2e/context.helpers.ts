import type { Page } from '@playwright/test';

// Contexto sintético estable para pruebas de integración; no es una acción de la UI.
export async function enterContext(page: Page) {
  await page
    .getByLabel('Contexto en inglés')
    .fill(
      'We use the language modeling approach described in [1] to improve a statistical machine translation system.',
    );
}

export async function chooseExample(page: Page) {
  await page.getByRole('button', { name: 'Explorar ejemplos', exact: true }).click();
  await page
    .getByRole('dialog', { name: 'Elige un ejemplo' })
    .locator('.example-card')
    .first()
    .click();
}
