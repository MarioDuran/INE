"""Experimental single-service entry point for Render Free.

It runs the existing database-backed queue worker within the same process
as the web app. The worker is NOT durable: Render suspends idle free web services,
restarts instances, and offers no background-worker guarantee on Free.
Use render-produccion.yaml for continuous processing with a paid worker.
"""
import logging
import os
import threading

# Import in the main thread: worker.py installs signal handlers at import time.
from . import worker
from .main import app

logger = logging.getLogger('observatorio.free_server')
_worker_thread = None

@app.on_event('startup')
def start_embedded_worker():
    global _worker_thread
    if _worker_thread is None:
        worker.running = True
        _worker_thread = threading.Thread(
            target=worker.main,
            name='experimental-free-worker',
            daemon=True,
        )
        _worker_thread.start()
        logger.warning('Experimental free worker started. Jobs may be interrupted when the instance sleeps.')

@app.on_event('shutdown')
def stop_embedded_worker():
    worker.running = False

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT','8000')),
                proxy_headers=True, workers=1)
