import os
import tempfile
from pathlib import Path

# Configure a throwaway database before importing application modules.
TEST_DB = Path(tempfile.gettempdir()) / f'observatorio-test-{os.getpid()}.db'
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'
os.environ['APP_SECRET'] = 'a-random-long-secret-for-automated-tests'
os.environ['ADMIN_PASSWORD'] = 'testing-admin-password'
os.environ['REVIEWER_PASSWORD'] = 'testing-reviewer-password'
os.environ['COOKIE_SECURE'] = 'false'
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.models import SessionLocal, Video, Mention
from app.pipeline import ExtendedFields
from app.transcripts import youtube_id, parse_timed_text, timed_groups
from app.definitions import CATEGORIES

SRT='''1
00:00:10,000 --> 00:00:15,000
Hoy se presentó una propuesta de seguridad.

2
00:00:15,000 --> 00:00:19,000
La persona invitada explicó su propuesta.
'''

def test_youtube_url_validation():
    assert youtube_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=15') == 'dQw4w9WgXcQ'
    assert youtube_id('https://youtu.be/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'
    assert youtube_id('https://www.youtube.com/live/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'
    for bad in ['https://bad.example/watch?v=dQw4w9WgXcQ',
                'https://www.youtube.com.evil.org/watch?v=dQw4w9WgXcQ',
                'http://169.254.169.254/latest', 'javascript:alert(1)']:
        try:youtube_id(bad)
        except ValueError:pass
        else:assert False,bad

def test_caption_parsing():
    rows=parse_timed_text(SRT)
    assert len(rows)==2
    assert rows[0]['start']==10
    assert rows[1]['end']==19
    try:parse_timed_text('Texto sin tiempos')
    except ValueError:pass
    else:assert False

def test_windowing():
    from types import SimpleNamespace
    s=[SimpleNamespace(ordinal=i+1,start=i*10.0,end=(i+1)*10.0,text='ejemplo') for i in range(140)]
    wins=timed_groups(s)
    assert len(wins)==3
    assert wins[0]['start']==0 and wins[1]['start']==600
    assert any(x.ordinal==61 for x in wins[0]['segments'])

def test_metadata_has_25_categories():
    assert len(CATEGORIES)==25
    assert len(set(k for k,v in CATEGORIES))==25

def test_auth_import_review_analytics():
    if TEST_DB.exists():TEST_DB.unlink()
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        assert client.get('/').status_code==303 or client.get('/').status_code==200
        assert client.post('/api/videos/import',json={}).status_code==401 or client.post('/api/videos/import',json={}).status_code==403
        r=client.post('/login',data={'username':'admin','password':'testing-admin-password'},follow_redirects=False)
        assert r.status_code==303
        home=client.get('/')
        assert home.status_code==200 and 'Panorama general' in home.text
        import re
        token=re.search(r'name="csrf-token" content="([^"]+)"',home.text).group(1)
        data={'urls':'https://www.youtube.com/watch?v=dQw4w9WgXcQ','stage':'prueba',
              'medium':'television','date':'2026-10-28','program':'Prueba institucional'}
        assert client.post('/api/videos/import',json=data).status_code==403
        created=client.post('/api/videos/import',json=data,headers={'X-CSRF-Token':token})
        assert created.status_code==200,created.text
        vid=created.json()['added'][0]
        assert client.get(f'/videos/{vid}').status_code==200
        response=client.post(f'/api/videos/{vid}/transcript',json={'text':SRT},headers={'X-CSRF-Token':token})
        assert response.status_code==200,response.text
        with SessionLocal.begin() as db:
            mention=Mention(video_id=vid,start=10,end=15,speaker='Conductora',subject='Persona de prueba',
                 quote='Hoy se presentó una propuesta de seguridad.',context='Ejemplo neutral.',
                 genre='entrevista',topic='seguridad',tone='neutra',findings=[],evidence_segments=[1],status='pending')
            db.add(mention);db.flush();mid=mention.id
        assert client.get(f'/review/{mid}').status_code==200
        payload={'start':10,'end':15,'speaker':'Conductora','subject':'Persona de prueba',
            'quote':'Hoy se presentó una propuesta de seguridad.','context':'Ejemplo neutral.',
            'genre':'entrevista','topic':'seguridad','tone':'neutra','findings':[],
            'review_note':'Verificado contra fuente de prueba','status':'approved'}
        payload['extra_data']={
          'speaker_gender':'no_especificado','subject_gender':'no_especificado',
          'speaker_role':'no_especificado','subject_role':'no_especificado',
          'party':'no_especificado','candidacy':'no_especificado',
          'participation_type':'entrevista','source_type':'no_especificado',
          'location':'no_especificado','schedule':'matutino','interruptions':0,
          'poll_mentioned':False,'pollster':'no_especificado',
          'poll_methodology':'no_aplica','poll_date':'no_especificado',
          'adjectives':[],'inclusive_language':'no_determinable','affirmative_action':'no_aplica'
        }
        response=client.post(f'/api/mentions/{mid}/review',json=payload,headers={'X-CSRF-Token':token})
        assert response.status_code==200,response.text
        analysis=client.get('/analytics?stage=prueba')
        assert analysis.status_code==200 and 'MENCIONES VALIDADAS' in analysis.text
        csv=client.get('/export/mentions.csv?stage=prueba')
        assert csv.status_code==200 and 'Persona de prueba' in csv.text
        # Official metrics must exclude test recordings.
        official=client.get('/analytics?stage=oficial')
        assert official.status_code==200 and 'Proceso oficial' in official.text
        assert client.post(f'/api/videos/{vid}/retry',json={},headers={'X-CSRF-Token':token}).status_code==409
        assert client.post('/api/logout',json={},headers={'X-CSRF-Token':token}).status_code==200
        assert client.get('/review',follow_redirects=False).status_code==303
