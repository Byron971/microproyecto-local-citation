// Reescritura antes de consultar S3, sin convertir errores de assets en HTML.
function handler(event) {
  var request = event.request;
  var path = request.uri;
  if (path.indexOf('/assets/') !== 0 && path.indexOf('/api/') !== 0 && path !== '/api' && path.split('/').pop().indexOf('.') === -1) {
    request.uri = '/index.html';
  }
  return request;
}
