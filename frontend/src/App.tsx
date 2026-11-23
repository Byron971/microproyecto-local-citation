import { Link, Navigate, Route, Routes, useLocation } from 'react-router';
import { useEffect, useState } from 'react';
import { HelpDialog } from './components/HelpDialog';
import { ScientificAnalysis } from './pages/ScientificAnalysis';

export function App() {
  const [helpOpen, setHelpOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = `${pathname === '/' ? 'Analizar una cita' : 'Página no encontrada'} · Citas académicas`;
  }, [pathname]);
  return (
    <>
      <a className="skip-link" href="#main">
        Ir al contenido
      </a>
      <header className="app-header">
        <div className="header-inner">
          <Link to="/" className="brand" aria-label="Análisis de citas, inicio">
            <svg viewBox="0 0 48 48" width="42" height="42" aria-hidden="true">
              <path
                d="M34.2 14.4A14 14 0 1 0 34.2 33.6"
                fill="none"
                stroke="currentColor"
                strokeWidth="6.5"
              />
              <circle cx="37.6" cy="24" r="4" fill="currentColor" />
            </svg>
            <span>Análisis de citas académicas</span>
          </Link>
          <nav className="compact-nav" aria-label="Navegación principal">
            <button
              type="button"
              className="header-help"
              aria-haspopup="dialog"
              onClick={() => setHelpOpen(true)}
            >
              Ayuda
            </button>
          </nav>
        </div>
      </header>
      <main id="main" className="main-content">
        <Routes>
          <Route path="/" element={<ScientificAnalysis />} />
          {[
            '/datos',
            '/modelo',
            '/negativos',
            '/fragmentos',
            '/funcion',
            '/funcion-b',
            '/analisis-ms',
          ].map((path) => (
            <Route key={path} path={path} element={<Navigate to="/" replace />} />
          ))}
          <Route
            path="*"
            element={
              <div className="empty-state">
                <h1>Página no encontrada</h1>
                <p>La dirección no corresponde a una vista de la aplicación.</p>
                <Link to="/">Volver al análisis</Link>
              </div>
            }
          />
        </Routes>
      </main>
      {helpOpen && <HelpDialog onClose={() => setHelpOpen(false)} />}
      <footer className="app-footer">
        <span>Recomendación local de citas académicas</span>
        <span>Corpus ACL-200 · Textos en inglés</span>
      </footer>
    </>
  );
}
