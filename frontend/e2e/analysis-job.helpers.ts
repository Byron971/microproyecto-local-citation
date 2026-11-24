// Respuestas simuladas del contrato de trabajos M/S (POST /trabajos, GET /trabajos/{id}).
export const JOB_ID = 'a'.repeat(32);
export const isAnalysisStart = (path: string) => path.endsWith('/api/analisis-cita-ms/trabajos');
export const isAnalysisRead = (path: string) =>
  /\/api\/analisis-cita-ms\/trabajos\/[a-f0-9]{32}$/.test(path);
export const job = (estado: string, extra: Record<string, unknown> = {}) => ({
  trabajo_id: JOB_ID,
  estado,
  creado_en: 1,
  espera_maxima_s: 900,
  retencion_s: 3600,
  ...extra,
});
export const completedJob = (resultado: unknown) => job('completado', { resultado });
