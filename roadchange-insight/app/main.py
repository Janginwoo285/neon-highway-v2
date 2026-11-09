"""RoadChange Insight full-stack API / static frontend.
Demo prototype. Do not upload identifiable proprietary vehicle data without authorization.
"""
import csv, hashlib, hmac, io, json, os, re, secrets, time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, Response, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
from .db import init_db, get_db, User, LoginSession, RoadChange, DriveClip, GpsPoint, MatchRun, Candidate, AuditLog
from .seed import seed_demo
from .matching import match_clips

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
UPLOAD = ROOT.parent / 'data' / 'uploads'
UPLOAD.mkdir(parents=True,exist_ok=True)
IS_HTTPS = os.getenv('COOKIE_SECURE','false').lower() == 'true'
ENABLE_DEMO = os.getenv('ENABLE_DEMO','true').lower() == 'true'
DISABLE_VIDEO_UPLOADS = os.getenv('DISABLE_VIDEO_UPLOADS','false').lower() == 'true'
SESSION_SECONDS = 7*24*60*60

def now(): return datetime.now(timezone.utc).isoformat()
def pw_hash(password):
    salt=secrets.token_bytes(16)
    dk=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000)
    return f"pbkdf2_sha256:310000:{salt.hex()}:{dk.hex()}"
def pw_valid(password,encoded):
    try:
        alg,rounds,salt,key=encoded.split(':')
        if alg!='pbkdf2_sha256': return False
        return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds)),bytes.fromhex(key))
    except Exception: return False

def private_user(request:Request, db:Session=Depends(get_db)):
    token=request.cookies.get('rci_session')
    if not token: raise HTTPException(401,'로그인이 필요합니다.')
    sess=db.get(LoginSession,hashlib.sha256(token.encode()).hexdigest())
    if not sess or sess.expires_at<now(): raise HTTPException(401,'로그인이 만료되었습니다.')
    user=db.get(User,sess.user_id)
    if user is None: raise HTTPException(401,'계정 정보를 찾을 수 없습니다.')
    return user

def audit(db,uid,act,detail):
    db.add(AuditLog(user_id=uid,action=act,detail=detail,at=now()))

def set_auth(resp:Response,db:Session,user:User):
    token=secrets.token_urlsafe(36)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,expires_at=(datetime.now(timezone.utc)+timedelta(seconds=SESSION_SECONDS)).isoformat()))
    db.commit()
    resp.set_cookie('rci_session',token,max_age=SESSION_SECONDS,httponly=True,samesite='lax',secure=IS_HTTPS,path='/')
    return {'authenticated':True,'user':{'id':user.id,'name':user.name,'email':user.email}}

class Credentials(BaseModel):
    email:str=Field(min_length=5,max_length=255)
    password:str=Field(min_length=8,max_length=128)
    name:str=Field(default='',max_length=100)
class NewChange(BaseModel):
    name:str=Field(min_length=3,max_length=200)
    kind:Literal['임시 차선','차로 폐쇄','진입로 변경','공사 구간']
    latitude:float=Field(ge=-90,le=90)
    longitude:float=Field(ge=-180,le=180)
    observed_at:datetime
    radius_m:float=Field(default=550,ge=50,le=3000)
    description:str=Field(default='',max_length=500)
class RunReq(BaseModel):
    change_id:int
    radius_m:float=Field(default=550,ge=50,le=3000)
    window_days:int=Field(default=7,ge=1,le=30)
class ReviewReq(BaseModel):
    status:Literal['accepted','rejected','hold']
    note:str=Field(min_length=3,max_length=800)

app=FastAPI(title='RoadChange Insight API',description='도로 변경 기반 주행 데이터 후보 탐색 MVP (합성 시연 데이터)',version='1.0.0')
init_db()

@app.get('/api/health')
def health(): return {'ok':True,'service':'RoadChange Insight','mode':'prototype'}

@app.get('/api/auth/me')
def me(request:Request,db:Session=Depends(get_db)):
    try:
        u=private_user(request,db)
        return {'authenticated':True,'user':{'id':u.id,'name':u.name,'email':u.email}}
    except HTTPException: return {'authenticated':False,'user':None}

@app.post('/api/auth/register')
def register(payload:Credentials,response:Response,db:Session=Depends(get_db)):
    email=payload.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise HTTPException(422,'올바른 이메일을 입력하세요.')
    if len(payload.password)<8: raise HTTPException(422,'비밀번호는 8자 이상이어야 합니다.')
    if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,'이미 등록된 이메일입니다.')
    user=User(name=payload.name.strip() or email.split('@')[0],email=email,password_hash=pw_hash(payload.password),created_at=now())
    db.add(user);db.flush();audit(db,user.id,'register','회원가입 완료')
    return set_auth(response,db,user)

@app.post('/api/auth/login')
def login(payload:Credentials,response:Response,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==payload.email.strip().lower()))
    if not user or not pw_valid(payload.password,user.password_hash): raise HTTPException(401,'이메일 또는 비밀번호가 올바르지 않습니다.')
    audit(db,user.id,'login','로그인')
    return set_auth(response,db,user)

@app.post('/api/auth/demo')
def demo(response:Response,db:Session=Depends(get_db)):
    if not ENABLE_DEMO:raise HTTPException(403,'공개 환경에서는 체험 계정 생성이 비활성화되어 있습니다.')
    name='데모 분석가'
    user=User(name=name,email=f"demo-{secrets.token_hex(7)}@example.invalid",password_hash=pw_hash(secrets.token_urlsafe(25)),created_at=now())
    db.add(user);db.flush();seed_demo(db,user.id);audit(db,user.id,'seed_demo','합성 위치·GPS·영상 샘플 생성')
    return set_auth(response,db,user)

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,db:Session=Depends(get_db)):
    token=request.cookies.get('rci_session')
    if token:
        s=db.get(LoginSession,hashlib.sha256(token.encode()).hexdigest())
        if s:db.delete(s);db.commit()
    response.delete_cookie('rci_session')
    return {'ok':True}

@app.post('/api/demo/seed')
def seed_for_user(db:Session=Depends(get_db),user:User=Depends(private_user)):
    if not ENABLE_DEMO:raise HTTPException(403,'사용할 수 없습니다.')
    if db.scalar(select(RoadChange.id).where(RoadChange.user_id==user.id)):
        raise HTTPException(409,'이미 도로 변경 데이터가 있습니다. 기존 기록을 보호하기 위해 추가하지 않았습니다.')
    seed_demo(db,user.id)
    audit(db,user.id,'seed_demo','합성 데모 데이터 생성');db.commit()
    return {'ok':True}

def change_dict(x):return {'id':x.id,'code':x.code,'name':x.name,'kind':x.kind,'latitude':x.latitude,'longitude':x.longitude,'observed_at':x.observed_at,'radius_m':x.radius_m,'description':x.description,'source':x.source}
def clip_dict(x):return {'id':x.id,'code':x.code,'trip_id':x.trip_id,'start_at':x.start_at,'end_at':x.end_at,'source':x.source,'has_video':bool(x.video_path)}

@app.get('/api/summary')
def summary(db:Session=Depends(get_db),u:User=Depends(private_user)):
    count=lambda table: db.scalar(select(func.count()).select_from(table).where(table.user_id==u.id)) or 0
    return {'changes':count(RoadChange),'clips':count(DriveClip),'runs':count(MatchRun),'candidates':count(Candidate),'accepted':db.scalar(select(func.count()).select_from(Candidate).where(Candidate.user_id==u.id,Candidate.review_status=='accepted')) or 0,'user_name':u.name,'mode':'합성·업로드 데이터 시연','demo_enabled':ENABLE_DEMO,'video_uploads_enabled':not DISABLE_VIDEO_UPLOADS}

@app.get('/api/changes')
def changes(db:Session=Depends(get_db),u:User=Depends(private_user)):
    return [change_dict(x) for x in db.scalars(select(RoadChange).where(RoadChange.user_id==u.id).order_by(RoadChange.id)).all()]

@app.post('/api/changes',status_code=201)
def create_change(payload:NewChange,db:Session=Depends(get_db),u:User=Depends(private_user)):
    code=f"RC-{secrets.token_hex(3).upper()}"
    v=payload.model_dump(); v['observed_at']=payload.observed_at.isoformat()
    change=RoadChange(user_id=u.id,code=code,source='manual',**v)
    db.add(change);db.flush();d=change_dict(change);audit(db,u.id,'create_change',code);db.commit();return d

@app.get('/api/clips')
def clips(db:Session=Depends(get_db),u:User=Depends(private_user)):
    return [clip_dict(x) for x in db.scalars(select(DriveClip).where(DriveClip.user_id==u.id).order_by(DriveClip.id.desc())).all()]

@app.post('/api/matches/run')
def run_match(payload:RunReq,db:Session=Depends(get_db),u:User=Depends(private_user)):
    change=db.scalar(select(RoadChange).where(RoadChange.id==payload.change_id,RoadChange.user_id==u.id))
    if not change:raise HTTPException(404,'변경 구간을 찾을 수 없습니다.')
    clip_list=db.scalars(select(DriveClip).where(DriveClip.user_id==u.id)).all()
    points_by_clip={c.id:db.scalars(select(GpsPoint).where(GpsPoint.clip_id==c.id)).all() for c in clip_list}
    matches=match_clips(change,clip_list,points_by_clip,payload.radius_m,payload.window_days)
    run=MatchRun(user_id=u.id,change_id=change.id,radius_m=payload.radius_m,window_days=payload.window_days,created_at=now())
    db.add(run);db.flush()
    for m in matches:
        db.add(Candidate(user_id=u.id,run_id=run.id,clip_id=m['clip'].id,change_id=change.id,matched_at=m['matched_at'],distance_m=m['distance_m'],score=m['score'],is_duplicate=m['is_duplicate'],review_status='pending'))
    audit(db,u.id,'match_run',f"{change.code} / 후보 {len(matches)}건 / 반경 {payload.radius_m}m / 관측 이후 {payload.window_days}일")
    db.commit()
    return {'run_id':run.id,'change_id':change.id,'count':len(matches),'duplicates':sum(1 for x in matches if x['is_duplicate'])}

def candidate_dict(c,clip,change):
    return {'id':c.id,'run_id':c.run_id,'clip_id':c.clip_id,'clip_code':clip.code,'trip_id':clip.trip_id,'change_id':c.change_id,'change_name':change.name,'distance_m':c.distance_m,'matched_at':c.matched_at,'score':c.score,'is_duplicate':c.is_duplicate,'review_status':c.review_status,'review_note':c.review_note,'reviewed_at':c.reviewed_at,'source':clip.source,'has_video':bool(clip.video_path)}

@app.get('/api/candidates')
def candidates(change_id:int|None=None,db:Session=Depends(get_db),u:User=Depends(private_user)):
    stmt=select(Candidate).where(Candidate.user_id==u.id)
    if change_id is not None:stmt=stmt.where(Candidate.change_id==change_id)
    rows=db.scalars(stmt.order_by(Candidate.id.desc())).all()
    # Latest run by each event; prior runs remain in DB/audit but are not double-counted.
    latest={}
    for c in rows:latest.setdefault(c.change_id,c.run_id)
    return [candidate_dict(c,db.get(DriveClip,c.clip_id),db.get(RoadChange,c.change_id)) for c in rows if c.run_id==latest[c.change_id]]

@app.post('/api/candidates/{candidate_id}/review')
def review(candidate_id:int,payload:ReviewReq,db:Session=Depends(get_db),u:User=Depends(private_user)):
    c=db.scalar(select(Candidate).where(Candidate.id==candidate_id,Candidate.user_id==u.id))
    if not c:raise HTTPException(404,'검수 후보를 찾을 수 없습니다.')
    if c.is_duplicate and payload.status=='accepted':
        raise HTTPException(409,'중복 후보는 확정할 수 없습니다. 중복 확인 후 제외·보류로 분류하세요.')
    c.review_status=payload.status;c.review_note=payload.note.strip();c.reviewed_at=now()
    audit(db,u.id,'review',f"후보 {c.id} {payload.status} / {payload.note.strip()[:120]}");db.commit()
    return {'ok':True,'id':c.id,'review_status':c.review_status}

@app.get('/api/audit')
def audit_logs(db:Session=Depends(get_db),u:User=Depends(private_user)):
    logs=db.scalars(select(AuditLog).where(AuditLog.user_id==u.id).order_by(desc(AuditLog.id)).limit(30)).all()
    return [{'id':l.id,'action':l.action,'detail':l.detail,'at':l.at} for l in logs]

@app.get('/api/export')
def export_data(format:Literal['csv','json']='csv',db:Session=Depends(get_db),u:User=Depends(private_user)):
    all_rows=db.scalars(select(Candidate).where(Candidate.user_id==u.id,Candidate.review_status=='accepted').order_by(Candidate.id.desc())).all()
    latest_by_change={}
    # Evaluate latest run by change independent of review state.
    for r in db.scalars(select(MatchRun).where(MatchRun.user_id==u.id).order_by(desc(MatchRun.id))).all(): latest_by_change.setdefault(r.change_id,r.id)
    records=[]
    for c in all_rows:
        if latest_by_change.get(c.change_id)!=c.run_id:continue
        change=db.get(RoadChange,c.change_id);clip=db.get(DriveClip,c.clip_id)
        records.append({'change_code':change.code,'change_type':change.kind,'road_change_observed_at':change.observed_at,'clip_code':clip.code,'trip_id':clip.trip_id,'matched_at':c.matched_at,'min_distance_m':c.distance_m,'match_score':c.score,'review_status':c.review_status,'reviewed_at':c.reviewed_at,'review_note':c.review_note,'source':clip.source})
    audit(db,u.id,'export',f'{format} {len(records)}건');db.commit()
    if format=='json':
        return Response(content=json.dumps({'source':'RoadChange Insight MVP','warning':'도로 변경 발생 시점은 검증 전이며 영상 학습 적합성은 수동 검수 결과입니다.','records':records},ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="roadchange_accepted.json"'})
    out=io.StringIO();out.write('\ufeff')
    keys=['change_code','change_type','road_change_observed_at','clip_code','trip_id','matched_at','min_distance_m','match_score','review_status','reviewed_at','review_note','source']
    writer=csv.DictWriter(out,fieldnames=keys);writer.writeheader();writer.writerows(records)
    return Response(content=out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="roadchange_accepted.csv"'})

@app.get('/api/clips/{clip_id}/video')
def clip_video(clip_id:int,db:Session=Depends(get_db),u:User=Depends(private_user)):
    clip=db.scalar(select(DriveClip).where(DriveClip.id==clip_id,DriveClip.user_id==u.id))
    if not clip or not clip.video_path:raise HTTPException(404,'영상이 없습니다.')
    if clip.source=='synthetic-demo':
        path=STATIC/'media'/Path(clip.video_path).name
    else:
        path=UPLOAD/str(u.id)/Path(clip.video_path).name
    if not path.is_file():raise HTTPException(404,'영상 파일을 찾을 수 없습니다.')
    return FileResponse(path,media_type='video/mp4',headers={'Cache-Control':'private, max-age=300'})

@app.post('/api/clips/{clip_id}/video')
async def upload_video(clip_id:int, file:UploadFile=File(...),db:Session=Depends(get_db),u:User=Depends(private_user)):
    if DISABLE_VIDEO_UPLOADS: raise HTTPException(503,'무료 클라우드 환경에서는 영상 파일의 영구 저장을 지원하지 않습니다. 합성 샘플 영상으로 시연해 주세요.')
    clip=db.scalar(select(DriveClip).where(DriveClip.id==clip_id,DriveClip.user_id==u.id))
    if not clip:raise HTTPException(404,'주행 로그를 찾을 수 없습니다.')
    if not file.filename or Path(file.filename).suffix.lower()!='.mp4':raise HTTPException(400,'MP4 영상만 업로드할 수 있습니다.')
    folder=UPLOAD/str(u.id);folder.mkdir(parents=True,exist_ok=True)
    dest=folder/(secrets.token_hex(15)+'.mp4');size=0
    try:
        with dest.open('wb') as out:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>35*1024*1024:raise HTTPException(413,'영상은 35MB 이하만 허용됩니다.')
                out.write(chunk)
        if size<12 or dest.open('rb').read(12)[4:8]!=b'ftyp':raise HTTPException(400,'올바른 MP4 파일이 아닙니다.')
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    if clip.source=='uploaded-video':
        old=folder/Path(clip.video_path).name
        old.unlink(missing_ok=True)
    clip.video_path=dest.name;clip.source='uploaded-video';audit(db,u.id,'video_upload',clip.code);db.commit()
    return {'ok':True,'clip_id':clip.id,'bytes':size}

@app.post('/api/import/logs')
async def import_logs(file:UploadFile=File(...),db:Session=Depends(get_db),u:User=Depends(private_user)):
    """CSV schema: clip_code, trip_id, sampled_at, latitude, longitude. grouped by clip."""
    data=await file.read(1024*1024+1)
    if len(data)>1024*1024:raise HTTPException(413,'CSV 파일은 1MB 이하만 허용됩니다.')
    try:
        content=data.decode('utf-8-sig');rows=list(csv.DictReader(io.StringIO(content)))
        required={'clip_code','trip_id','sampled_at','latitude','longitude'}
        if not rows or not required.issubset(rows[0].keys()) or len(rows)>3000:raise ValueError('CSV 컬럼 또는 행 수가 올바르지 않습니다.')
        grouped={}
        for r in rows:
            k=(r['clip_code'].strip()[:40],r['trip_id'].strip()[:60]);lat=float(r['latitude']);lon=float(r['longitude'])
            if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError('좌표 범위 오류')
            from .matching import dt
            t=dt(r['sampled_at']).isoformat()
            if not k[0] or not k[1]:raise ValueError('필수 값 누락')
            grouped.setdefault(k,[]).append((t,lat,lon))
        for (code,trip),points in grouped.items():
            points.sort()
            c=DriveClip(user_id=u.id,code=code,trip_id=trip,start_at=points[0][0],end_at=points[-1][0],video_path='',source='uploaded-csv')
            db.add(c);db.flush()
            for t,lat,lon in points:db.add(GpsPoint(clip_id=c.id,sampled_at=t,latitude=lat,longitude=lon))
        audit(db,u.id,'import_logs',f'{len(grouped)}개 클립 / {len(rows)}개 GPS 행')
        db.commit()
        return {'ok':True,'clips':len(grouped),'points':len(rows)}
    except (ValueError,KeyError,UnicodeDecodeError) as e:
        db.rollback();raise HTTPException(422,f'CSV 형식 오류: {e}')

@app.get('/api/download/demo-csv')
def demo_csv():
    path=ROOT.parent/'demo_data'/'sample_gps.csv'
    return FileResponse(path,media_type='text/csv',filename='sample_gps.csv')

@app.get('/',response_class=HTMLResponse)
def index():return FileResponse(STATIC/'index.html')

app.mount('/static',StaticFiles(directory=str(STATIC)),name='static')
