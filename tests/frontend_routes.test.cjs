const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync('terraform/frontend/routes.js', 'utf8'), context);
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
