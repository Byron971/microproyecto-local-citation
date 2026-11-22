"""Descubrimiento de modelos y cola secuencial reanudable con presupuesto local conservador."""
import json
import importlib.util
import os
import re
import sys
from contextlib import contextmanager, ExitStack
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import anotacion_asistida as aa


@contextmanager
def connected_clients(providers=('openai', 'anthropic')):
    """Solo usa claves presentes en la sesión; no solicita ni muestra secretos."""
    with ExitStack() as stack:
        clients = {}
        for provider in providers:
            env = 'ANTHROPIC_API_KEY' if provider == 'anthropic' else 'OPENAI_API_KEY'
            if not os.getenv(env):
                print(f'{provider} omitido: falta {env} en la sesión del kernel.')
                continue
            sdk = 'anthropic' if provider == 'anthropic' else 'openai'
            if importlib.util.find_spec(sdk) is None:
                print(f'Falta el SDK {sdk} en el kernel {sys.executable}. '
                      f'Ejecuta %pip install --upgrade {sdk} y vuelve a ejecutar la conexión.')
                continue
            context = aa._anthropic_client if provider == 'anthropic' else aa._openai_client
            try:
                clients[provider] = stack.enter_context(context())
            except (RuntimeError, ImportError, TypeError, ValueError) as exc:
                print(f'No se creó cliente {provider} ({type(exc).__name__}); '
                      f'kernel: {sys.executable}. Ejecuta %pip install --upgrade {sdk} '
                      'y reinicia el kernel. No se muestran claves ni detalles de la solicitud.')
        yield clients


@contextmanager
def configuration(**changes):
    previous = aa.CONFIG.copy()
    aa.CONFIG.update(changes)
    try:
        yield
    finally:
        aa.CONFIG.clear()
        aa.CONFIG.update(previous)


def candidate(provider, model):
    if provider == 'anthropic':
        return model.startswith('claude-')
    if not re.match(r'^(gpt-|chatgpt-|o[134](?:-|$))', model):
        return False
    return not any(s in model for s in ('audio', 'realtime', 'transcribe', 'tts', 'image',
                                         'search', 'codex', 'computer', 'deep-research', '-pro'))


def discover(clients):
    """models.list se pagina al iterar el SDK. No hace inferencia ni presume compatibilidad."""
    rows = []
    errors = []
    for provider, client in clients.items():
        try:
            for model in client.models.list():
                model_id = model.id
                eligible = candidate(provider, model_id) and getattr(model, 'lifecycle', None) != 'retired'
                rows.append({'provider': provider, 'model': model_id, 'candidate': eligible,
                             'status': 'por_comprobar' if eligible else 'fuera_del_flujo',
                             'note': 'El listado no garantiza permisos de inferencia ni JSON estructurado.'})
        except Exception as exc:
            errors.append({'provider': provider, 'status': 'error_listado',
                           'error_type': type(exc).__name__, 'http_status': getattr(exc, 'status_code', None)})
    unique = {(r['provider'], r['model']): r for r in rows}
    return sorted(unique.values(), key=lambda r: (r['provider'], r['model'])), errors


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Reserva antes de cada intento, incluso fallido. No representa facturación oficial.

    Concilia contra tokens informados; sin uso mantiene la reserva. Reanudar usa el mismo
    archivo. Una sesión por archivo, sin concurrencia.
    Tokens de entrada: heurística conservadora de bytes*2 + margen. Puede detenerse antes
    de gastar el saldo real; no garantiza la factura de servicios externos ni incluye impuestos.
    """
    def __init__(self, path, limit=20, already_spent=0):
        self.path = Path(path)
        self.limit = Decimal(str(limit))
        if not self.limit.is_finite() or self.limit < 0 or self.limit > 20:
            raise ValueError('El límite debe estar entre 0 y 20 USD.')
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {
            'already_spent_usd': str(already_spent), 'reservations': []}
        spent = Decimal(self.data['already_spent_usd'])
        if not spent.is_finite() or spent < 0:
            raise ValueError('Gasto inicial inválido.')
        if Decimal(str(already_spent)) != spent:
            raise ValueError('El gasto inicial difiere del registro existente; no reiniciar el presupuesto.')
        self.stopped = False

    @property
    def reserved(self):
        return Decimal(self.data['already_spent_usd']) + sum(
            (Decimal(r['usd']) for r in self.data['reservations']), Decimal(0))

    @staticmethod
    def usage_cost(usage, rate):
        """Costo estándar calculado; no descuenta caché ni sustituye la factura."""
        if not isinstance(usage, dict):
            return None
        incoming = usage.get('prompt_tokens', usage.get('input_tokens'))
        outgoing = usage.get('completion_tokens', usage.get('output_tokens'))
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in (incoming, outgoing)):
            return None
        # Anthropic separa los tokens de escritura/lectura de caché. Sin sus tarifas,
        # conservar reserva; no subestimar escrituras tratándolas como entrada estándar.
        if usage.get('cache_creation_input_tokens') or usage.get('cache_read_input_tokens'):
            return None
        return (incoming * Decimal(str(rate[0])) + outgoing * Decimal(str(rate[1]))) / Decimal(1000000)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        aa._write_atomic(self.path, json.dumps(self.data, indent=2).encode())

    def settle(self, index, usage, rate, response_id=None):
        cost = self.usage_cost(usage, rate)
        if cost is None:
            return False
        record = self.data['reservations'][index]
        record.setdefault('reserved_usd_original', record['usd'])
        record.update(usd=str(cost), usage=usage, rate_per_million=list(rate),
                      response_id=response_id, accounting='reported_tokens_estimated_cost')
        self._save()
        return True

    def reconcile_logs(self, paths, rates):
        """Migra reservas antiguas solo con correspondencia completa por modelo y orden.

        El ledger antiguo carece de IDs de solicitud: exigir un solo log por modelo,
        conteos idénticos y respuestas únicas. Si no coincide, conservar las reservas.
        """
        from collections import defaultdict
        groups, logs = defaultdict(list), defaultdict(list)
        for index, record in enumerate(self.data['reservations']):
            groups[(record['provider'], record['model'])].append(index)
        for path in dict.fromkeys(Path(p) for p in paths):
            entries = aa.read_log(path)
            models = {(r.get('provider', 'openai'), r.get('model')) for r in entries if r.get('usage')}
            for key in models:
                logs[key].append((path, [r for r in entries if (r.get('provider','openai'),r.get('model')) == key and r.get('usage')]))
        changes = []
        for key, indices in groups.items():
            if key not in rates or len(logs[key]) != 1:
                continue
            path, entries = logs[key][0]
            response_ids = [r.get('response_id') for r in entries]
            if len(entries) != len(indices) or not all(response_ids) or len(set(response_ids)) != len(entries):
                continue
            for index, entry in zip(indices, entries):
                record = self.data['reservations'][index]
                if record.get('accounting'):
                    continue
                cost = self.usage_cost(entry['usage'], rates[key])
                if cost is not None:
                    changes.append((index, entry, rates[key], str(path)))
        if changes:
            backup = self.path.with_name(self.path.stem + '.antes_conciliacion.json')
            if not backup.exists():
                with backup.open('xb') as f:
                    f.write(self.path.read_bytes())
            for index, entry, rate, path in changes:
                self.settle(index, entry['usage'], rate, entry['response_id'])
                self.data['reservations'][index]['reconciled_from'] = path
            self._save()
        return len(changes)

    def reserve(self, provider, model, rate, request, output_tokens):
        self.stopped = False
        rates = [Decimal(str(v)) for v in rate]
        if len(rates) != 2 or any(not v.is_finite() or v < 0 for v in rates):
            raise ValueError('Tarifas deben ser entrada/salida no negativas, USD por millón de tokens.')
        input_bound = len(json.dumps(request, ensure_ascii=False).encode('utf-8')) * 2 + 20000
        usd = (input_bound * rates[0] + output_tokens * rates[1]) / Decimal(1000000)
        if self.reserved + usd > self.limit:
            self.stopped = True
            raise BudgetExceeded('Reserva local agotada; no se envió este intento.')
        self.data['reservations'].append({'provider': provider, 'model': model, 'usd': str(usd),
                                           'input_token_estimate': input_bound, 'output_token_cap': output_tokens})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        aa._write_atomic(self.path, json.dumps(self.data, indent=2).encode())
        return len(self.data['reservations']) - 1


def guarded_client(client, provider, model, rate, budget, output_tokens):
    native = client.messages.create if provider == 'anthropic' else client.chat.completions.create

    def create(**kwargs):
        index = budget.reserve(provider, model, rate, kwargs, output_tokens)
        response = native(**kwargs)
        usage = getattr(response, 'usage', None)
        if usage is not None:
            budget.settle(index, usage.model_dump(), rate, getattr(response, 'id', None))
        return response

    if provider == 'anthropic':
        return SimpleNamespace(messages=SimpleNamespace(create=create))
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def run_all(source, catalog, clients, rates, folder, budget, *, max_output_tokens=2048,
            progress=print, run=aa.run):
    """Intenta todos los candidatos con tarifa conocida; reporta exclusiones y errores.

    La primera entrada de cada modelo funciona como prueba real de compatibilidad y
    se conserva. HTTP 400/403/404 detiene ese modelo, no los demás. Reanuda por sus logs.
    """
    if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
        raise ValueError('Límite de tokens inválido.')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    summary, predictions = [], []
    aa._write_atomic(folder / 'resumen_multimodelo.json', json.dumps({
        'results': [], 'reserved_usd': str(budget.reserved), 'limit_usd': str(budget.limit)
    }).encode())
    for row in catalog:
        provider, model = row['provider'], row['model']
        record = {'provider': provider, 'model': model, 'status': 'excluido'}
        summary.append(record)
        with configuration(provider=provider, model=model):
            existing = aa.output_path(source)
        if existing.is_file():
            record.update(status='omitido_archivo_existente', output=str(existing))
            progress(f'Omitido {model}: ya existe {existing.name}')
            saved = existing.with_suffix('.predicciones.json')
            if saved.is_file():
                try:
                    data = json.loads(saved.read_text(encoding='utf-8'))
                    if data['source_sha256'] == aa.digest(Path(source).read_bytes()) and data['model'] == model:
                        predictions.append(saved)
                        record.update(predictions=str(saved), completed=len(data['results']), total=len(data['context_ids']))
                except (OSError, ValueError, KeyError):
                    record['note'] = 'No se pudo leer la predicción auxiliar; el Excel permanece intacto.'
        elif not row['candidate']:
            record['status'] = 'fuera_del_flujo'
        elif provider not in clients:
            record['status'] = 'sin_cliente'
        elif rates.get((provider, model)) is None:
            record['status'] = 'falta_tarifa'
        else:
            with configuration(provider=provider, model=model, temperature=None,
                               anthropic_max_tokens=max_output_tokens,
                               openai_max_completion_tokens=max_output_tokens):
                template = aa.read_template(source)
                proxy = guarded_client(clients[provider], provider, model, rates[(provider, model)],
                                       budget, max_output_tokens)
                progress(f'Procesando {provider}: {model}')
                try:
                    report = run(source, client=proxy, progress=progress)
                    record['status'] = 'sin_resultados' if report is None else 'procesado'
                except Exception as exc:
                    record.update(status='presupuesto_agotado' if budget.stopped else 'error_modelo',
                                  error_type=type(exc).__name__)
                    # No se vuelca str(exc): puede contener texto fuente o detalles de credenciales.
                # Incluso si un error corta la ejecución, exportar el avance válido de ese modelo.
                try:
                    log = aa.log_path_for(template)
                    state = aa.load_state(template, log)
                    if state['proposals']:
                        report = aa.export(template, log, state,
                                           aa.output_path(source, template=template))
                        record.update(predictions=str(report['predictions']), output=str(report['output']),
                                      completed=len(state['proposals']), total=len(template['cases']))
                        predictions.append(report['predictions'])
                        if record['status'] == 'procesado' and len(state['proposals']) < len(template['cases']):
                            record['status'] = 'parcial'
                except Exception as exc:
                    record['export_error_type'] = type(exc).__name__
        aa._write_atomic(folder / 'resumen_multimodelo.json', json.dumps({
            'results': summary, 'reserved_usd': str(budget.reserved), 'limit_usd': str(budget.limit),
            'note': 'Reserva estimada; consultar facturación. Listado no equivale a compatibilidad.'
        }, ensure_ascii=False, indent=2).encode())
    return summary, predictions
