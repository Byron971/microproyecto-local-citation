"""One transient analysis; polling never starts inference or calls a provider."""
import logging
import re
import threading
import time
import uuid

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from src.app.ms_lock import LOCK


class AnalysisJobs:
    def __init__(self, ttl=120, capacity=8, clock=time.monotonic):
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self.guard = threading.Lock()
        self.jobs = {}
        self.active = None

    def prune(self):
        for key, entry in list(self.jobs.items()):
            if entry.get('expires', float('inf')) <= self.clock():
                del self.jobs[key]

    def submit(self, operation):
        with self.guard:
            self.prune()
            if self.active is not None:
                raise HTTPException(429, 'El servicio científico está ocupado', headers={'Retry-After':'5'})
            while len(self.jobs) >= self.capacity:
                del self.jobs[next(iter(self.jobs))]
            key = uuid.uuid4().hex
            entry = {}
            self.jobs[key] = entry
            self.active = key
        ready = threading.Event()
        admitted = threading.Event()

        def run():
            outcome = {}
            acquired = LOCK.acquire(blocking=False)
            try:
                if not acquired:
                    raise HTTPException(429, 'El servicio científico está ocupado', headers={'Retry-After':'5'})
                admitted.set()
                ready.set()  # The worker owns the existing inference lock before POST returns.
                result = operation()
                outcome['result'] = result
            except HTTPException as exc:
                outcome['error'] = (exc.status_code, exc.detail, exc.headers)
            except Exception:
                logging.getLogger(__name__).exception('Error al ejecutar análisis científico')
                outcome['error'] = (503, 'No se pudo completar el análisis científico.')
            finally:
                if acquired:
                    LOCK.release()
                with self.guard:
                    entry.update(outcome)
                    entry['expires'] = self.clock() + self.ttl
                    self.active = None
                ready.set()
                timer = threading.Timer(self.ttl, self.expire, args=(key,))
                timer.daemon = True
                timer.start()

        try:
            threading.Thread(target=run, daemon=True, name='citation-analysis').start()
        except RuntimeError:
            with self.guard:
                self.jobs.pop(key, None)
                self.active = None
            raise HTTPException(503, 'No se pudo iniciar el análisis.') from None
        ready.wait(timeout=2)
        with self.guard:
            error = entry.get('error')
        if error and not admitted.is_set():
            raise HTTPException(*error)
        return self.pending(key)

    def expire(self, key):
        with self.guard:
            entry = self.jobs.get(key)
            if entry and entry.get('expires', float('inf')) <= self.clock():
                self.jobs.pop(key, None)

    @staticmethod
    def pending(key):
        return JSONResponse({'estado':'procesando', 'trabajo_id':key}, status_code=202)

    def read(self, key):
        with self.guard:
            self.prune()
            entry = self.jobs.get(key) if re.fullmatch(r'[a-f0-9]{32}', key) else None
            if entry is None:
                raise HTTPException(410, 'El análisis expiró o el servicio se reinició. Vuelve a analizar; tu contexto se conserva.')
            if 'error' in entry:
                raise HTTPException(*entry['error'])
            if 'result' in entry:
                return entry['result']
            return self.pending(key)


JOBS = AnalysisJobs()
