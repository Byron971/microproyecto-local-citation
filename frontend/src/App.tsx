import { NavLink, Route, Routes, useLocation, Link } from 'react-router';
import { useEffect, useRef } from 'react';
import { Recommend } from './pages/Recommend';
import { Analytics } from './pages/Analytics';
import { Top3 } from './pages/Top3';
export function App() {
  const { pathname } = useLocation();
  const explore = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (explore.current) explore.current.open = false;
    const names: Record<string, string> = {
      '/': 'Recomendar',
      '/datos': 'Datos',
      '/modelo': 'Desempeño',
      '/negativos': 'Negativos',
      '/fragmentos': 'Top-3',
    };
    document.title = `${names[pathname] || 'Página no encontrada'} · Recomendación local de citas académicas`;
  }, [pathname]);
  return (
    <>
      <a className="skip-link" href="#main">
        Ir al contenido
      </a>
      <header className="app-header">
        <div className="header-inner">
          <Link
            to="/"
            className="brand"
            aria-label="Recomendación local de citas académicas, inicio"
          >
            <svg viewBox="0 0 48 48" width="42" height="42" aria-hidden="true">
              <path
                d="M34.2 14.4A14 14 0 1 0 34.2 33.6"
                fill="none"
                stroke="currentColor"
                strokeWidth="6.5"
              />
              <circle cx="37.6" cy="24" r="4" fill="currentColor" />
            </svg>
            <span>
              Recomendación local<span className="brand-subtitle">de citas académicas</span>
            </span>
          </Link>
          <nav className="compact-nav" aria-label="Navegación principal">
            <NavLink to="/" end>
              Recomendar
            </NavLink>
            <details
              className="explore-menu"
              ref={explore}
              onKeyDown={(e) => {
                if (e.key === 'Escape' && explore.current) {
                  explore.current.open = false;
                  explore.current.querySelector('summary')?.focus();
                }
              }}
              onBlur={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node))
                  e.currentTarget.open = false;
              }}
            >
              <summary>Explorar</summary>
              <div className="explore-links">
                <NavLink to="/fragmentos">Fragmentos Top-3 · experimental</NavLink>
                <NavLink to="/datos">Datos</NavLink>
                <NavLink to="/modelo">Desempeño</NavLink>
                <NavLink to="/negativos">Negativos</NavLink>
              </div>
            </details>
          </nav>
        </div>
      </header>
      <main id="main" className="main-content">
        <Routes>
          <Route path="/" element={<Recommend />} />
          <Route path="/fragmentos" element={<Top3 />} />
          <Route path="/datos" element={<Analytics view="datos" />} />
          <Route path="/modelo" element={<Analytics view="modelo" />} />
          <Route path="/negativos" element={<Analytics view="negativos" />} />
          <Route
            path="*"
            element={
              <div className="empty-state">
                <h1>Página no encontrada</h1>
                <p>La dirección no corresponde a una vista de la aplicación.</p>
                <Link to="/">Volver al recomendador</Link>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="app-footer">
        <span>Recomendación local de citas académicas</span>
        <span>Corpus ACL-200 · Textos en inglés</span>
      </footer>
    </>
  );
}
