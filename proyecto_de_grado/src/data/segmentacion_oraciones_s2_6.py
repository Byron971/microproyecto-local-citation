"""Segmentacion S2.6 conservadora, trazable y orientada a oraciones.

La deteccion de oraciones es heuristica: si no hay frontera inequívoca antes
 de un limite, se rechaza el parrafo en vez de partir una oracion.
"""
from __future__ import annotations

import re

# Heuristica deliberadamente conservadora para prosa cientifica en ingles.
_FRONTERA = re.compile(r'[.!?][\)\]\}\"\'\u201d\u2019]*\s+(?=\S)')
_ABREVIATURAS = frozenset({
    'al', 'dr', 'mr', 'mrs', 'ms', 'prof', 'fig', 'figs', 'eq', 'eqs',
    'sec', 'secs', 'ref', 'refs', 'vs', 'cf', 'no', 'nos', 'vol', 'pp',
    'approx', 'etc', 'i.e', 'e.g', 'et al',
})


def _posibles_oraciones(texto: str) -> list[tuple[int, int]]:
    """Devuelve offsets contiguos sin borrar espacios ni normalizar el texto."""
    cortes = [0]
    for coincidencia in _FRONTERA.finditer(texto):
        # La puntuacion que ha disparado la coincidencia debe cerrar frase.
        signo = coincidencia.group(0)[0]
        if signo == '.':
            antes = texto[:coincidencia.start() + 1]
            simple = re.search(r'([A-Za-z]+)\.$', antes)
            unidad = simple.group(1).lower() if simple else ''
            if unidad in _ABREVIATURAS or antes.lower().endswith('et al.'):
                continue
            # Siglas como U.S. o N.L.P. no son fronteras confiables.
            if re.search(r'(?:\b[A-Z]\.){2,}$', antes):
                continue
            # Evitar 'e.g.'/'i.e.' incluso si el token final es una letra.
            if re.search(r'\b(?:e\.g|i\.e)\.$', antes, re.IGNORECASE):
                continue
        despues = texto[coincidencia.end():]
        if not despues:
            continue
        # Frase siguiente empieza por mayuscula, digito, o cita/comilla.
        proximo = despues[0]
        if not (proximo.isupper() or proximo.isdigit() or proximo in '\"\'([{\u201c\u2018'):
            continue
        cortes.append(coincidencia.end())
    cortes.append(len(texto))
    return [(inicio, fin) for inicio, fin in zip(cortes, cortes[1:]) if fin > inicio]


def dividir_parrafo_oraciones(parrafo: dict, max_palabras: int, max_caracteres: int) -> list[dict]:
    """Agrupa oraciones completas con límites de palabras y caracteres.

    Rechaza oraciones individuales mayores al límite; no utiliza un fallback
    de corte por palabras. Los offsets son rangos [start, end) del original.
    """
    texto = parrafo['texto']
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError('Parrafo sin texto para segmentar por oraciones.')
    oraciones = _posibles_oraciones(texto)
    if not oraciones:
        raise ValueError('Parrafo sin oraciones interpretables.')
    rangos = []
    inicio = 0
    for ini, fin in oraciones:
        unidad = texto[ini:fin]
        if len(unidad.split()) > max_palabras or len(unidad) > max_caracteres:
            raise ValueError(
                f'oracion_extensa_sin_corte_seguro: parrafo={parrafo["numero"]}; '
                f'palabras={len(unidad.split())}; caracteres={len(unidad)}'
            )
        nuevo = texto[inicio:fin]
        if len(nuevo.split()) > max_palabras or len(nuevo) > max_caracteres:
            rangos.append((inicio, ini))
            inicio = ini
    rangos.append((inicio, len(texto)))
    if any(not texto[a:b].strip() for a,b in rangos):
        raise ValueError('Segmento vacio tras segmentacion de oraciones.')
    if ''.join(texto[a:b] for a,b in rangos) != texto:
        raise ValueError('Segmentacion por oraciones con perdida de texto.')
    return [{
        'numero': parrafo['numero'],
        'seccion': parrafo['seccion'],
        'texto': texto[a:b],
        'segmento': j,
        'char_inicio': a,
        'char_fin': b,
    } for j,(a,b) in enumerate(rangos)]
