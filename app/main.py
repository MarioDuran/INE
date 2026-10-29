import csv
import io
import json
import secrets
from collections import Counter, defaultdict
from datetime import datetime, date
from functools import wraps
from urllib.parse import urlencode
from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from .config import APP_SECRET, ADMIN_PASSWORD, REVIEWER_PASSWORD, COOKIE_SECURE, OPENAI_MODEL
from .models import SessionLocal, Video, Segment, Mention, Job, Audit, init_db, now
from .transcripts import youtube_id, parse_timed_text
from .pipeline import load_segments, ExtendedFields
from .definitions import CATEGORIES, CATEGORY_IDS, STAGES, MEDIA, GENRES, TOPICS

app=FastAPI(title='Observatorio de Medios | Monitoreo Electoral',docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory='app/static'),name='static')
templates=Jinja2Templates(directory='app/templates')

@app.on_event('startup')
def startup():
    init_db()
    if COOKIE_SECURE and (not ADMIN_PASSWORD or not REVIEWER_PASSWORD or APP_SECRET=='unsafe-local-development-secret'):
        raise RuntimeError('En producción configura ADMIN_PASSWORD, REVIEWER_PASSWORD y APP_SECRET.')

def get_db():
    with SessionLocal() as session:yield session

def user_or_none(request:Request):
    return request.session.get('user')

def require_user(request: Request):
    user=user_or_none(request)
    if not user:raise HTTPException(status_code=401,detail='Inicia sesión para continuar')
    return user

def require_admin(request:Request):
    user=require_user(request)
    if user!='admin':raise HTTPException(status_code=403,detail='Solo administración')
    return user

@app.middleware('http')
async def security(request,call_next):
    if request.method in ('POST','PUT','PATCH','DELETE') and request.url.path not in ('/login',):
        sess=request.session
        csrf=sess.get('csrf')
        if not csrf or not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),csrf):
            return JSONResponse({'detail':'CSRF token ausente o inválido'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Frame-Options']='DENY'
    return response

app.add_middleware(SessionMiddleware,secret_key=APP_SECRET,https_only=COOKIE_SECURE,max_age=8*60*60,same_site='lax')

def page(request:Request,name:str,**data):
    return templates.TemplateResponse(request,name,{'request':request,'user':user_or_none(request),
        'csrf':request.session.get('csrf',''),'categories':CATEGORIES,'stages':STAGES,'media':MEDIA,
        'genres':GENRES,'topics':TOPICS,'model_name':OPENAI_MODEL,**data})

def public_or_login(request:Request):
    if not user_or_none(request):return RedirectResponse('/login',status_code=303)
    return None

@app.get('/health')
def health():return {'status':'ok'}

@app.get('/login',response_class=HTMLResponse)
def login_page(request:Request):
    if user_or_none(request):return RedirectResponse('/',status_code=303)
    return page(request,'login.html',error='')

@app.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...)):
    if username=='admin' and ADMIN_PASSWORD and secrets.compare_digest(password,ADMIN_PASSWORD):role='admin'
    elif username=='revisor' and REVIEWER_PASSWORD and secrets.compare_digest(password,REVIEWER_PASSWORD):role='revisor'
    else:return page(request,'login.html',error='Credenciales incorrectas.')
    request.session.clear();request.session.update({'user':role,'csrf':secrets.token_urlsafe(32)})
    return RedirectResponse('/',status_code=303)

@app.post('/api/logout')
def logout(request:Request,user=Depends(require_user)):
    request.session.clear()
    return {'redirect':'/login'}

@app.get('/',response_class=HTMLResponse)
def dashboard(request:Request,db:Session=Depends(get_db)):
    jump=public_or_login(request)
    if jump:return jump
    videos=db.scalars(select(Video).order_by(Video.created_at.desc()).limit(50)).all()
    video_total=db.scalar(select(func.count(Video.id))) or 0
    mentions_total=db.scalar(select(func.count(Mention.id))) or 0
    pending=db.scalar(select(func.count(Mention.id)).where(Mention.status=='pending')) or 0
    approved=db.scalar(select(func.count(Mention.id)).where(Mention.status=='approved')) or 0
    return page(request,'dashboard.html',videos=videos,metrics={'videos':video_total,'mentions':mentions_total,'pending':pending,'approved':approved})

@app.get('/videos/new',response_class=HTMLResponse)
def new_video(request:Request):
    jump=public_or_login(request)
    if jump:return jump
    if user_or_none(request)!='admin':raise HTTPException(403,'Solo administración')
    return page(request,'new.html',today=date.today().isoformat())

class VideoBatch(BaseModel):
    urls: str = Field(min_length=10,max_length=20000)
    stage: str
    medium: str
    date: str
    program: str = Field(default='',max_length=160)

@app.post('/api/videos/import')
def import_videos(payload:VideoBatch,db:Session=Depends(get_db),user=Depends(require_admin)):
    if payload.stage not in dict(STAGES) or payload.medium not in dict(MEDIA):raise HTTPException(422,'Etapa o medio inválido')
    try:date.fromisoformat(payload.date)
    except ValueError:raise HTTPException(422,'Fecha inválida')
    raw_urls=[x.strip() for x in payload.urls.splitlines() if x.strip()]
    if len(raw_urls)>50:raise HTTPException(422,'Máximo 50 URLs por carga')
    if not raw_urls:raise HTTPException(422,'Ingresa al menos una URL')
    parsed=[];errors=[]
    for url in raw_urls:
        try:parsed.append((youtube_id(url),url))
        except ValueError as e:errors.append({'url':url,'error':str(e)})
    if errors:raise HTTPException(422,detail={'urls_invalidas':errors})
    added=[];duplicates=[]
    for vid,url in parsed:
        if db.scalar(select(Video.id).where(Video.youtube_id==vid)):
            duplicates.append(vid);continue
        record=Video(youtube_id=vid,youtube_url=f'https://www.youtube.com/watch?v={vid}',
          title=f'Video {vid}',medium=payload.medium,stage=payload.stage,program=payload.program,
          date=payload.date,status='queued')
        db.add(record);db.flush()
        db.add(Job(video_id=record.id,kind='fetch',status='queued'))
        db.add(Audit(actor=user,action='video_created',entity='video',entity_id=record.id,
            old_values={},new_values={'youtube_id':vid,'stage':payload.stage}))
        added.append(record.id)
    db.commit()
    return {'added':added,'duplicates':duplicates}

@app.get('/videos/{video_id}',response_class=HTMLResponse)
def video_page(request:Request,video_id:int,db:Session=Depends(get_db)):
    jump=public_or_login(request)
    if jump:return jump
    video=db.get(Video,video_id)
    if not video:raise HTTPException(404,'Video inexistente')
    seg_count=db.scalar(select(func.count(Segment.id)).where(Segment.video_id==video_id)) or 0
    mentions=db.scalars(select(Mention).where(Mention.video_id==video_id).order_by(Mention.start)).all()
    segments=db.scalars(select(Segment).where(Segment.video_id==video_id).order_by(Segment.ordinal).limit(100)).all()
    jobs=db.scalars(select(Job).where(Job.video_id==video_id).order_by(Job.id.desc()).limit(5)).all()
    return page(request,'video.html',video=video,segments=segments,seg_count=seg_count,mentions=mentions,jobs=jobs)

class TranscriptPayload(BaseModel):
    text: str = Field(min_length=20,max_length=3_000_000)

@app.post('/api/videos/{video_id}/transcript')
def upload_transcript(video_id:int,payload:TranscriptPayload,db:Session=Depends(get_db),user=Depends(require_admin)):
    video=db.get(Video,video_id)
    if not video:raise HTTPException(404,'Video inexistente')
    if video.status=='processing':raise HTTPException(409,'No reemplaces los subtítulos mientras se ejecuta el análisis.')
    try:rows=parse_timed_text(payload.text)
    except ValueError as e:raise HTTPException(422,str(e))
    try:load_segments(db,video,rows)
    except ValueError as e:raise HTTPException(409,str(e))
    # Cancel obsolete queued jobs (including automatic fetch for this video).
    for job in db.scalars(select(Job).where(Job.video_id==video_id,Job.status=='queued')):
        job.status='cancelled'
    db.add(Job(video_id=video_id,kind='analyze',status='queued'))
    db.add(Audit(actor=user,action='transcript_replaced',entity='video',entity_id=video_id,
       old_values={},new_values={'segments':len(rows)}))
    db.commit()
    return {'segments':len(rows),'status':'queued'}

@app.post('/api/videos/{video_id}/retry')
def retry(video_id:int,db:Session=Depends(get_db),user=Depends(require_admin)):
    video=db.get(Video,video_id)
    if not video:raise HTTPException(404,'Video inexistente')
    if video.status in ('fetching','processing'):raise HTTPException(409,'Hay un proceso activo')
    if db.scalar(select(Mention.id).where(Mention.video_id==video_id,Mention.status=='approved').limit(1)):
        raise HTTPException(409,'No se reprocesa un registro aprobado sin una nueva versión auditada.')
    has_segments=bool(db.scalar(select(Segment.id).where(Segment.video_id==video_id).limit(1)))
    jobkind='analyze' if has_segments else 'fetch'
    for job in db.scalars(select(Job).where(Job.video_id==video_id,Job.status=='queued')):job.status='cancelled'
    db.add(Job(video_id=video_id,kind=jobkind,status='queued'))
    video.status='queued';video.error=''
    db.commit()
    return {'queued':jobkind}

class ManualMention(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    speaker: str = Field(min_length=1,max_length=200)
    subject: str = Field(min_length=1,max_length=240)
    quote: str = Field(min_length=1,max_length=10000)

@app.post('/api/videos/{video_id}/mentions/manual')
def manual_mention(video_id:int,payload:ManualMention,db:Session=Depends(get_db),user=Depends(require_user)):
    v=db.get(Video,video_id)
    if not v:raise HTTPException(404,'Testigo inexistente')
    if payload.end<=payload.start or (v.duration_seconds and payload.end>v.duration_seconds+2):
        raise HTTPException(422,'Intervalo fuera de rango')
    mention=Mention(video_id=v.id,start=payload.start,end=payload.end,
                    speaker=payload.speaker,subject=payload.subject,quote=payload.quote,
                    context='Creada manualmente para corregir una omisión de la IA.',
                    status='pending',ai_model='registro_manual',ai_raw={'source':'human'})
    db.add(mention);db.flush()
    v.no_mentions=False;v.no_mentions_verified=False
    db.add(Audit(actor=user,action='missing_mention_added',entity='mention',entity_id=mention.id,
      old_values={},new_values=payload.model_dump()))
    db.commit()
    return {'id':mention.id,'status':'pending'}

@app.post('/api/videos/{video_id}/verify-no-mentions')
def verify_no_mentions(video_id:int,db:Session=Depends(get_db),user=Depends(require_user)):
    v=db.get(Video,video_id)
    if not v:raise HTTPException(404,'Testigo inexistente')
    if v.status!='ready':raise HTTPException(409,'Finaliza el análisis primero')
    if db.scalar(select(Mention.id).where(Mention.video_id==video_id,Mention.status!='rejected').limit(1)):
        raise HTTPException(409,'Existen menciones sin descartar. Revísalas antes.')
    v.no_mentions=True;v.no_mentions_verified=True;v.no_mentions_reviewer=user
    db.add(Audit(actor=user,action='no_mentions_verified',entity='video',entity_id=video_id,
       old_values={},new_values={'verified':True}))
    db.commit()
    return {'verified':True}

@app.get('/review',response_class=HTMLResponse)
def review_list(request:Request,status:str='pending',db:Session=Depends(get_db)):
    jump=public_or_login(request)
    if jump:return jump
    if status not in ('pending','approved','rejected','all'):status='pending'
    q=select(Mention).order_by(Mention.created_at.desc()).limit(300)
    if status!='all':q=q.where(Mention.status==status)
    mentions=db.scalars(q).all()
    videos={v.id:v for v in db.scalars(select(Video).where(Video.id.in_({x.video_id for x in mentions}))).all()} if mentions else {}
    return page(request,'reviews.html',mentions=mentions,videos=videos,status_filter=status)

@app.get('/review/{mention_id}',response_class=HTMLResponse)
def mention_page(request:Request,mention_id:int,db:Session=Depends(get_db)):
    jump=public_or_login(request)
    if jump:return jump
    mention=db.get(Mention,mention_id)
    if not mention:raise HTTPException(404,'Mención inexistente')
    video=db.get(Video,mention.video_id)
    segments=db.scalars(select(Segment).where(Segment.video_id==video.id,
        Segment.end >= max(mention.start-25,0),Segment.start <= mention.end+25).order_by(Segment.ordinal)).all()
    return page(request,'mention.html',mention=mention,video=video,segments=segments)

class FindingEdit(BaseModel):
    category: str
    evidence: str = Field(max_length=3000)
    explanation: str = Field(max_length=4000)

class MentionEdit(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    speaker: str = Field(min_length=1,max_length=200)
    subject: str = Field(min_length=1,max_length=240)
    quote: str = Field(min_length=1,max_length=10000)
    context: str = Field(max_length=12000)
    genre: str
    topic: str
    tone: str
    findings: list[FindingEdit] = Field(max_length=30)
    extra_data: ExtendedFields
    review_note: str = Field(default='',max_length=5000)
    status: str

@app.post('/api/mentions/{mention_id}/review')
def save_mention(mention_id:int,payload:MentionEdit,db:Session=Depends(get_db),user=Depends(require_user)):
    mention=db.get(Mention,mention_id)
    if not mention:raise HTTPException(404,'Mención inexistente')
    video=db.get(Video,mention.video_id)
    if payload.status not in ('pending','approved','rejected'):raise HTTPException(422,'Estado inválido')
    if payload.end<=payload.start:raise HTTPException(422,'El fin debe ser mayor que el inicio')
    if video.duration_seconds and payload.end>video.duration_seconds+2:raise HTTPException(422,'El intervalo rebasa la duración disponible')
    if payload.genre not in dict(GENRES) or payload.topic not in dict(TOPICS):raise HTTPException(422,'Género o tema inválido')
    if payload.tone not in ('positiva','negativa','neutra','no_aplica'):raise HTTPException(422,'Valoración inválida')
    if any(f.category not in CATEGORY_IDS or not f.evidence.strip() or not f.explanation.strip() for f in payload.findings):
        raise HTTPException(422,'Cada hallazgo requiere categoría, frase y justificación')
    fields=['start','end','speaker','subject','quote','context','genre','topic','tone','findings','review_note','status']
    old={field:getattr(mention,field) for field in fields}
    old['extra_data']=mention.extra_data
    new=payload.model_dump()
    for field in fields:setattr(mention,field,new[field])
    mention.extra_data=payload.extra_data.model_dump()
    if payload.status!='pending':mention.reviewer=user;mention.reviewed_at=now()
    else:mention.reviewer='';mention.reviewed_at=None
    db.add(Audit(actor=user,action='mention_review',entity='mention',entity_id=mention_id,
      old_values=old,new_values=new))
    db.commit()
    return {'status':'saved','mention_id':mention_id}

@app.get('/analytics',response_class=HTMLResponse)
def analytics(request:Request,stage:str='oficial',db:Session=Depends(get_db)):
    jump=public_or_login(request)
    if jump:return jump
    q=select(Mention,Video).join(Video,Mention.video_id==Video.id).where(Mention.status=='approved')
    if stage=='oficial':q=q.where(Video.stage!='prueba')
    elif stage in dict(STAGES):q=q.where(Video.stage==stage)
    else:stage='oficial';q=q.where(Video.stage!='prueba')
    rows=db.execute(q).all()
    videos=db.scalars(select(Video).where(Video.stage!='prueba' if stage=='oficial' else Video.stage==stage)).all()
    total_hrs=sum(v.duration_seconds for v in videos)/3600
    by_stage=Counter(dict(STAGES).get(v.stage,v.stage) for m,v in rows)
    by_topic=Counter(dict(TOPICS).get(m.topic,m.topic) for m,v in rows)
    by_subject=Counter(m.subject for m,v in rows)
    by_medium=Counter(dict(MEDIA).get(v.medium,v.medium) for m,v in rows)
    by_day=Counter(v.date for m,v in rows)
    by_tone=Counter(m.tone for m,v in rows)
    by_category=Counter(dict(CATEGORIES).get(f.get('category'),f.get('category')) for m,v in rows for f in (m.findings or []))
    unique_video_count=len(set(m.video_id for m,v in rows))
    stats={'mentions':len(rows),'videos_total':len(videos),'videos_with_mentions':unique_video_count,
           'hours':round(total_hrs,1),'rate':round(len(rows)/total_hrs,2) if total_hrs else 0}
    return page(request,'analytics.html',stage_filter=stage,stats=stats,
        by_stage=by_stage,by_topic=by_topic,by_subject=by_subject,by_medium=by_medium,by_day=by_day,
        by_tone=by_tone,by_category=by_category)

@app.get('/export/mentions.csv')
def export_mentions(request:Request,stage:str='oficial',db:Session=Depends(get_db),user=Depends(require_user)):
    q=select(Mention,Video).join(Video).where(Mention.status=='approved')
    if stage=='oficial':q=q.where(Video.stage!='prueba')
    elif stage in dict(STAGES):q=q.where(Video.stage==stage)
    else:raise HTTPException(422,'Etapa desconocida')
    buf=io.StringIO();writer=csv.writer(buf)
    writer.writerow(['id','fecha','etapa','medio','programa','youtube_url','inicio_segundos','fin_segundos',
                     'quien_habla','a_quien_se_refiere','cita','contexto','genero_periodistico','tema',
                     'valoracion','variables_complementarias_json','hallazgos_json','revisor','fecha_revision'])
    for m,v in db.execute(q.order_by(Video.date,Mention.start)):
        writer.writerow([m.id,v.date,v.stage,v.medium,v.program,v.youtube_url,m.start,m.end,
          m.speaker,m.subject,m.quote,m.context,m.genre,m.topic,m.tone,
          json.dumps(m.extra_data,ensure_ascii=False),json.dumps(m.findings,ensure_ascii=False),
          m.reviewer,m.reviewed_at.isoformat() if m.reviewed_at else ''])
    buf.seek(0)
    # UTF-8 BOM for Excel, no spreadsheet formula injection on user-authored fields.
    content=buf.getvalue()
    safe_lines=[]
    # csv writer above is for trusted spreadsheet program use. Neutralize potential injection in text values.
    dst=io.StringIO();out=csv.writer(dst)
    for row in csv.reader(io.StringIO(content)):
        out.writerow(["'"+cell if cell.lstrip().startswith(('=','+','-','@')) and not cell.replace('-','',1).replace('.','',1).isdigit() else cell for cell in row])
    return StreamingResponse(iter(['\ufeff'+dst.getvalue()]),media_type='text/csv; charset=utf-8',
          headers={'Content-Disposition':'attachment; filename="menciones-validadas.csv"','Cache-Control':'no-store'})

@app.get('/api/videos/{video_id}/state')
def video_state(video_id:int,db:Session=Depends(get_db),user=Depends(require_user)):
    v=db.get(Video,video_id)
    if not v:raise HTTPException(404)
    return {'status':v.status,'error':v.error,'mentions':db.scalar(select(func.count(Mention.id)).where(Mention.video_id==v.id)) or 0}
