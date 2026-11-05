# John — Issue #119: QA externo, paquete Word/PDF y gate de entrega

Fecha de preparación: 4 de noviembre de 2026. **ESTADO: BORRADOR / NO ENTREGAR**.

## Estado verificado y lo que NO debe afirmarse

- La [ejecución Docker E2E del PR #131](https://github.com/Byron971/microproyecto-local-citation/actions/runs/41959273085) terminó correctamente en GitHub Actions con **51 pruebas y 13 comprobaciones HTTP** (sobre un runner de CI). Eso valida infraestructura y baseline TF-IDF/BM25, **no una URL pública ni calidad científica del Top-3**.
- El PR #130 de parametrización y el PR #131 de integración técnica siguen sujetos a revisión/fusión, y este issue está apilado sobre ellos.
- **No hay en este manifiesto una URL externa HTTPS validada**. No inventarla. `localhost:8000` o `localhost:8080` no constituyen entrega pública.
- El endpoint final de SciBERT Top-3 y el de clasificación de nueve funciones **no estaban integrados al servicio** al elaborar este control. No confundir ramas científicas #102/#103 con inferencia desplegada.
- El Test Gold de nueve categorías y el Gold humano de chunks son pruebas científicas independientes que deben ser documentadas por sus responsables. Un smoke test no acredita precisión, F1 o Recall@3.

## Manifest de entrega

Archivo: `config/entrega_despliegue.example.json`.

Registra:
1. Título completo del proyecto y nombres de los cinco integrantes.
2. Enlace canónico del repositorio GitHub.
3. `application_url` y `api_url`: inicialmente `null`, deben ser URLs reales HTTPS, sin credenciales, privadas/locales de prueba ni texto inventado. Usar un DNS de acceso evaluable.
4. Instrucciones de acceso para el jurado **sin contraseñas**, tokens ni API keys en el repositorio.
5. Persona, fecha UTC y enlace a evidencia de una prueba de acceso desde **otra red**. Esto no se demuestra desde CI en localhost.
6. Evidencia del CI de contenedores y de funcionalidad final, diferenciadas.

**Nunca subir claves a JSON o PR.** Para acceso restringido compartir credenciales por canal institucional seguro.

## Comando de auditoría y borrador

```bash
python scripts/validar_paquete_entrega.py \
  --manifest config/entrega_despliegue.example.json \
  --output-dir artifacts/paquete_entrega
```

Genera:
- `auditoria.json`: condiciones, bloqueos y advertencias.
- `borrador_entrega.md`: documento de entrega preliminar que dice NO APTO mientras faltan requisitos.

Modo de bloqueo explícito:

```bash
python scripts/validar_paquete_entrega.py \
  --manifest config/entrega_despliegue.example.json \
  --strict
```

Devolverá código 2 mientras falten URL externa, prueba independiente y/o componentes finales. Para comprobar la URL desde el equipo que prepara la evidencia (no sustituye verificación desde **otra red**):

```bash
python scripts/validar_paquete_entrega.py \
  --manifest config/entrega_despliegue.example.json \
  --probe --output-dir artifacts/paquete_entrega
```

El smoke se ejecuta sobre la API de línea base del PR #131 y no valida aún los servicios científicos finales. Debe actualizarse al conectar modelos, sin desbloquear automáticamente la entrega por editar un campo del manifiesto.

## Word/PDF de la entrega

El documento breve a enviar a la universidad tiene que mencionar:
- Nombre completo del proyecto;
- los cinco integrantes;
- enlace GitHub clicable;
- enlace a aplicación **externa y verificada**;
- fecha/hora y responsable de la verificación;
- instrucciones de acceso sin secretos;
- descripción concreta de la inferencia que el evaluador puede probar;
- referencia de resultados de E2E y límites.

El borrador Word/PDF de acompañamiento tiene que quedar rotulado **NO ENTREGAR / PENDIENTE URL FINAL** hasta que #116 y #119 dispongan de evidencias externas. El validador no genera el Word/PDF definitivo, solo Markdown y JSON auditables; se produce la versión de envío al cerrar los bloqueos con pruebas reales. Verificar enlaces clicables y formato del Word/PDF.

## Rúbrica del despliegue — 100 puntos distintos del informe académico

| Criterio | Puntos | Evidencia necesaria |
|---|---:|---|
| Funcionamiento | 35 | API/modelo final + frontend + acceso externo y pruebas de casos reales |
| Reproducibilidad | 15 | README ejecutado desde clon, recursos y dependencias |
| Parametrización | 15 | Variables sin secretos y configuraciones probadas (#118) |
| Interfaz | 35 | Interacción comprensible con Top-3 y función de cita, explicación de límites y resultados |

## Controles P0 para cerrar

- [ ] PR #130 fusionado y PR #131 rebasado/revisado, sin conflictos.
- [ ] URL HTTPS real, comprobada desde una red externa, idealmente por un integrante distinto del desplegador.
- [ ] SciBERT Top-3 y clasificador de nueve funciones conectados a modelos/versiones reales.
- [ ] Casos normales, error 422, servicio caído, timeout y accesibilidad legible comprobados.
- [ ] CPU/memoria/latencia de despliegue final medidos con cargas representativas, no un solo request en CI.
- [ ] Seguridad: TLS, control de acceso, sin credenciales en archivos, logs o capturas.
- [ ] Word/PDF final con enlaces clicables y probados; acceso disponible en horario de evaluación.

**No cerrar #119 por un CI verde ni por un documento con enlaces vacíos.**
