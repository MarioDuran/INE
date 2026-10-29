import re
from urllib.parse import urlparse, parse_qs

YT_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')

def youtube_id(url: str) -> str:
    """Parse only supported YouTube hosts, never arbitrary remote URLs."""
    url = url.strip()
    u = urlparse(url)
    host = (u.hostname or '').lower()
    path = u.path.strip('/')
    if u.scheme not in ('https', 'http'):
        raise ValueError('URL no válida: utiliza https://youtube.com/watch?v=...')
    if host in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com'):
        if path == 'watch': video_id = parse_qs(u.query).get('v',[''])[0]
        elif path.startswith(('live/','shorts/','embed/')): video_id = path.split('/')[1]
        else: video_id = ''
    elif host in ('youtu.be','www.youtu.be'):
        video_id = path.split('/')[0]
    else:
        raise ValueError('Solo se aceptan enlaces de YouTube o youtu.be.')
    if not YT_ID.fullmatch(video_id):
        raise ValueError('No se encontró un ID de YouTube válido.')
    return video_id

TIMECODE = re.compile(r'(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})')

def as_seconds(timecode: str) -> float:
    m = TIMECODE.fullmatch(timecode.strip())
    if not m: raise ValueError(f'Tiempo inválido: {timecode}')
    hours, minutes, seconds, millis = m.groups()
    if int(seconds)>=60 or int(minutes)>=60 and hours: raise ValueError('Tiempo fuera de rango')
    return int(hours or 0)*3600 + int(minutes)*60 + int(seconds) + int(millis.ljust(3,'0'))/1000

RANGE = re.compile(r'((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})')

def parse_timed_text(raw: str) -> list[dict]:
    """Import SRT/VTT captions; reject non-timed text to preserve evidence precision."""
    text = raw.lstrip('\ufeff').replace('\r\n','\n').replace('\r','\n').strip()
    blocks = re.split(r'\n\s*\n', text)
    rows=[]
    for block in blocks:
        lines=block.strip().splitlines()
        for i,line in enumerate(lines):
            m=RANGE.search(line)
            if m:
                start, end=as_seconds(m.group(1)), as_seconds(m.group(2))
                spoken=' '.join(re.sub(r'<[^>]+>', '', l).strip() for l in lines[i+1:] if l.strip())
                if spoken and end>start:
                    rows.append({'start':start,'end':end,'text':spoken})
                break
    if not rows:
        raise ValueError('No encontré segmentos con tiempo. Pega un archivo SRT o VTT con inicio y fin por segmento.')
    rows.sort(key=lambda s:s['start'])
    return rows

def fetch_owned_caption(video_id: str) -> list[dict]:
    """Official Google OAuth flow for captions of videos editable by this account.

    Requires YouTube Data API v3 and a refresh token granted with youtube.force-ssl.
    Does not bypass access controls or fetch other creators' private captions.
    """
    import httpx
    from .config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
    if not all((YOUTUBE_CLIENT_ID,YOUTUBE_CLIENT_SECRET,YOUTUBE_REFRESH_TOKEN)):
        raise RuntimeError('La integración OAuth de YouTube para el canal propio no está configurada.')
    with httpx.Client(timeout=30,follow_redirects=False) as client:
        token=client.post('https://oauth2.googleapis.com/token',data={
           'client_id':YOUTUBE_CLIENT_ID,'client_secret':YOUTUBE_CLIENT_SECRET,
           'refresh_token':YOUTUBE_REFRESH_TOKEN,'grant_type':'refresh_token'})
        token.raise_for_status()
        access_token=token.json().get('access_token')
        if not access_token:raise RuntimeError('Google no entregó un token de acceso')
        headers={'Authorization':f'Bearer {access_token}'}
        tracks=client.get('https://www.googleapis.com/youtube/v3/captions',
            params={'part':'snippet','videoId':video_id},headers=headers)
        tracks.raise_for_status()
        options=tracks.json().get('items',[])
        options.sort(key=lambda t:(not t.get('snippet',{}).get('language','').startswith('es'),
           t.get('snippet',{}).get('trackKind')=='ASR'))
        if not options:raise RuntimeError('No hay subtítulos publicados para este video del canal autorizado.')
        for track in options:
            if track.get('snippet',{}).get('status','serving')=='failed':continue
            r=client.get('https://www.googleapis.com/youtube/v3/captions/'+track['id'],
                params={'tfmt':'vtt'},headers=headers)
            if r.status_code>=400:continue
            try:return parse_timed_text(r.text)
            except ValueError:continue
    raise RuntimeError('Google no permitió descargar ninguna pista de subtítulos en formato VTT.')

def fetch_youtube_transcript(video_id: str) -> list[dict]:
    # youtube-transcript-api is not official; cloud egress can be blocked.
    from youtube_transcript_api import YouTubeTranscriptApi
    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=['es','es-MX','en'])
    return [{'start':float(x.start),'end':float(x.start+x.duration),'text':str(x.text)} for x in fetched if str(x.text).strip() and x.duration>0]

def timed_groups(segments: list, window_seconds: int = 600, overlap_seconds: int = 25) -> list[dict]:
    """Each window contains source segments and a core interval for duplicate control."""
    if not segments: return []
    last=max(float(s.end) for s in segments)
    windows=[]
    core=0.0
    while core<last:
        core_end=core+window_seconds
        included=[s for s in segments if s.start < core_end+overlap_seconds and s.end >= max(0,core-overlap_seconds)]
        if included:
            windows.append({'start':core, 'end':core_end, 'segments':included})
        core=core_end
    return windows
