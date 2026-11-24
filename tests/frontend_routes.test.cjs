const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync('terraform/routes.js', 'utf8'), context);
test('React Router recibe rutas directas y páginas desconocidas sin extensión', () => {
  for (const uri of ['/', '/datos', '/datos/', '/modelo', '/negativos', '/fragmentos', '/no-existe']) {
    assert.equal(context.handler({ request: { uri } }).uri, '/index.html');
  }
});
test('assets y API no se convierten en HTML aunque no existan', () => {
  for (const uri of ['/assets/main.js', '/assets/inexistente', '/missing.css', '/api', '/api/estado', '/favicon.svg']) {
    assert.equal(context.handler({ request: { uri } }).uri, uri);
  }
});

test('el catálogo de modelos tiene índice propio y sus descargas no se reescriben a React', () => {
  for (const uri of ['/models', '/models/']) {
    assert.equal(context.handler({ request: { uri } }).uri, '/models/index.html');
  }
  for (const uri of ['/models/releases/v1/modelo-M.zip', '/models/releases/v1/manifest.json', '/models/no-existe']) {
    assert.equal(context.handler({ request: { uri } }).uri, uri);
  }
});
