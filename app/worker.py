"""Render background worker, database-backed queue; one DB row claimed per worker."""
import logging, signal, time
from sqlalchemy import select
from .models import SessionLocal, Job, Video, init_db, now
from .pipeline import ingest_video, analyze_video

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
log=logging.getLogger('observatorio.worker')
running=True

def stop(*args):
    global running
    running=False
signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)

def claim_job():
    with SessionLocal.begin() as session:
        job=session.scalar(select(Job).where(Job.status=='queued').order_by(Job.created_at,Job.id)
                           .with_for_update(skip_locked=True).limit(1))
        if not job:return None
        job.status='running';job.started_at=now();job.attempt+=1
        return job.id,job.video_id,job.kind

def execute_job(claim):
    job_id,video_id,kind=claim
    try:
        if kind=='fetch':ingest_video(video_id)
        elif kind=='analyze':analyze_video(video_id)
        else:raise RuntimeError('Tipo de trabajo desconocido')
        with SessionLocal.begin() as session:
            job=session.get(Job,job_id)
            job.status='done';job.completed_at=now()
        log.info('job %s finished (%s)',job_id,kind)
    except Exception as e:
        log.exception('Job %s failed',job_id)
        with SessionLocal.begin() as session:
            job=session.get(Job,job_id)
            job.status='failed';job.error=str(e)[:2000];job.completed_at=now()
            video=session.get(Video,video_id)
            if video:
                video.status='error';video.error=str(e)[:500]

def main():
    init_db()
    log.info('worker started')
    while running:
        try:
            item=claim_job()
            if item:execute_job(item)
            else:time.sleep(3)
        except Exception:
            log.exception('worker poll failed')
            time.sleep(10)
if __name__=='__main__':main()
