import { useEffect, useState } from 'react';
import { api, ApiError } from '../api';
export function Status() {
  const [state, setState] = useState('Conectando…');
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    async function poll() {
      try {
        const response = await api.status(controller.signal);
        if (controller.signal.aborted) return;
        if (response.listo) setState('Modelo listo');
        else if (++attempts < 12) {
          setState('El modelo se está cargando');
          timer = setTimeout(poll, 5000);
        } else setState('Servicio no disponible');
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 503 && ++attempts < 12) {
          setState('El modelo se está cargando');
          timer = setTimeout(poll, 5000);
        } else setState('Servicio no disponible');
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);
  return (
    <span className={`service-status ${state === 'Modelo listo' ? 'ready' : ''}`} role="status">
      <span className="status-dot" />
      {state}
    </span>
  );
}
