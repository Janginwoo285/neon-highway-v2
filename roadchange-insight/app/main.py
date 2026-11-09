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
from .db import init_db, get_db, User, LoginSession, RoadChange, DriveClip, GpsPoint, MatchRun, Candidate, AuditLog, BusinessScenario, PilotTrial, RiskEvidence
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

app=FastAPI(title='RoadChange Insight API',description='도로 변경 기반 주행 데이터 후보 탐색 MVP (합성 시연 데이터)',version='1.2.0')
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



# INVESTOR VALIDATION (prototype measurements are user-entered, not validated company data)
STRATEGY_SECTIONS = [
 {'n':'01','title':'고객','tag':'구매 의사 확인 필요','text':'초기 실증 대상: 현대차·기아–42dot 자율주행 데이터 개발 관련 조직. 예산 소유자, 실제 유료 구매 담당자 및 독립 계약 단위는 확인 필요.'},
 {'n':'02','title':'문제','tag':'실증 필요','text':'기존 이벤트 선별 및 Hard Example Mining을 보완하여 공사·임시 차로 변경의 위치·관측 시각을 단서로 비개입 유효 장면을 추가 확보할 수 있는지 검증한다. 현장 검수 방식은 가설.'},
 {'n':'03','title':'해결책','tag':'구현과 가정 구분','text':'도로 변경 정보를 주행 GPS·시각과 매칭해 후보를 찾고, 중복을 표시해 검수자가 유효 장면을 확정한다. 확정 메타데이터는 CSV·JSON으로 내보낸다. Agentic AI 자동 변경 탐지와 내부 학습 파이프라인 직접 연동은 미구현.'},
 {'n':'04','title':'고객 가치','tag':'실적 아닌 목표','text':'미발견 장면을 더 찾고 중복 탐색을 줄여 검수자의 시간을 모델 개선에 재배치한다. 20분에서 13.5분으로 줄이는 32.5% 단축은 측정 전 목표값.'},
 {'n':'05','title':'수익','tag':'가격 가정','text':'고객별 연 2,500만 원의 고정 연동·기술지원료를 가정한다. 유료 1·3·8개 고객 시나리오는 매출 추정일 뿐 구매 의사나 실제 국내 시장 규모를 의미하지 않는다.'},
 {'n':'06','title':'비용','tag':'미계상 비용 확인 필요','text':'초기 개발비 3,000만 원, 연 공통 운영비 1,000만 원, 고객당 연 기술지원비 1,000만 원을 가정한다. 영상 저장·보안·영업·실제 인프라 단가는 미확인.'},
 {'n':'07','title':'검증할 숫자','tag':'파일럿에서 측정','text':'기존/제안 방식의 ① 유효 장면 검수 통과율 ② 유효 장면 1건 확보 시간 ③ 중복 제외 고유 유효 건수 ④ 비개입 장면 추가 발견 여부를 같은 조건에서 비교한다. 연간 1만 건은 목표이며 실적이 아니다.'}
]
INVESTOR_RISKS = [
 {'code':'R1','title':'구매 조직과 예산 담당자 미확인','where':'고객 · 수익','question':'누가 연 2,500만 원의 지출을 승인하며, 실제 구매 의사를 확인했습니까?','action':'잠재 구매 담당자·계약 구조 확인'},
 {'code':'R2','title':'기존 선별 기술 대비 신규 발견 가치 미확인','where':'문제','question':'기존 Hard Example Mining이 찾지 못한 장면을 새 방식은 얼마나 발견합니까?','action':'같은 로그에서 기존 대비 추가 발견 건수 검증'},
 {'code':'R3','title':'시간 단축·통과율 목표 미검증','where':'해결책 · 가치','question':'20분→13.5분과 20%→40%를 같은 검수 조건에서 입증했습니까?','action':'검수 시도·확정 건수·투입 시간 기록'},
 {'code':'R4','title':'실제 지도·주행 로그 접근권한 미확인','where':'해결책 · 비용','question':'공간·시간 정합성, 사용권한, 보안 승인 과정을 확보했습니까?','action':'승인된 샘플과 실제 연동 가능성 확인'},
 {'code':'R5','title':'고객 8곳 근거 및 전체 원가 미확인','where':'수익 · 비용','question':'국내 잠재 고객 8개사의 산정 근거와 빠진 비용은 무엇입니까?','action':'고객 후보와 전체 원가 조사'}
]
class ScenarioInput(BaseModel):
    annual_price:int=Field(ge=0,le=10000000000)
    one_time_build:int=Field(ge=0,le=10000000000)
    annual_fixed:int=Field(ge=0,le=10000000000)
    annual_per_customer:int=Field(ge=0,le=10000000000)
    customer_count:int=Field(ge=0,le=1000)
class PilotInput(BaseModel):
    mode:Literal['baseline','proposal']
    label:str=Field(min_length=2,max_length=140)
    inspected:int=Field(ge=1,le=100000000)
    accepted:int=Field(ge=0,le=100000000)
    duplicate_count:int=Field(ge=0,le=100000000)
    reviewer_minutes:float=Field(gt=0,le=1000000000)
    no_intervention_accepted:int=Field(ge=0,le=100000000)
    evidence_note:str=Field(default='',max_length=1200)
class RiskInput(BaseModel):
    state:Literal['미확인','검증 중','증빙 확보']
    note:str=Field(default='',max_length=1200)

def scenario_view(s):
    n=s.customer_count
    revenue=n*s.annual_price
    expense=s.one_time_build+s.annual_fixed+n*s.annual_per_customer
    margin=s.annual_price-s.annual_per_customer
    return {'annual_price':s.annual_price,'one_time_build':s.one_time_build,'annual_fixed':s.annual_fixed,'annual_per_customer':s.annual_per_customer,'customer_count':n,'revenue':revenue,'first_year_expense':expense,'first_year_balance_before_unlisted_costs':revenue-expense,'break_even_customers':((s.one_time_build+s.annual_fixed+margin-1)//margin if margin>0 else None),'updated_at':s.updated_at}

def pilots_view(records):
    result={}
    for mode in ('baseline','proposal'):
        a=[r for r in records if r.mode==mode]
        inspected=sum(r.inspected for r in a)
        accepted=sum(r.accepted for r in a)
        minutes=sum(r.reviewer_minutes for r in a)
        result[mode]={'trials':len(a),'inspected':inspected,'accepted':accepted,'duplicate_count':sum(r.duplicate_count for r in a),'reviewer_minutes':minutes,'no_intervention_accepted':sum(r.no_intervention_accepted for r in a),'pass_rate_pct':round(100*accepted/inspected,2) if inspected else None,'minutes_per_accepted':round(minutes/accepted,2) if accepted else None}
    before=result['baseline']['minutes_per_accepted']
    after=result['proposal']['minutes_per_accepted']
    result['time_reduction_pct']=round(100*(before-after)/before,2) if before and after is not None else None
    return result

@app.get('/api/strategy')
def get_strategy(db:Session=Depends(get_db),u:User=Depends(private_user)):
    s=db.get(BusinessScenario,u.id)
    if s is None:
        s=BusinessScenario(user_id=u.id,updated_at=now())
        db.add(s);db.commit();db.refresh(s)
    notes={r.risk_code:r for r in db.scalars(select(RiskEvidence).where(RiskEvidence.user_id==u.id)).all()}
    risks=[{**r,'state':notes[r['code']].state if r['code'] in notes else '미확인','note':notes[r['code']].note if r['code'] in notes else ''} for r in INVESTOR_RISKS]
    return {'sections':STRATEGY_SECTIONS,'risks':risks,'scenario':scenario_view(s),'targets':{'baseline_minutes_per_accepted':20,'proposal_minutes_per_accepted':13.5,'baseline_pass_rate_pct':20,'proposal_pass_rate_pct':40,'annual_unique_accepted':10000},'sources':[{'title':'현대오토에버 정밀지도 소개','url':'https://www.hyundai-autoever.com/kor/business-area/in-vehicle-it/precision-map/contents.do?cntnSeq=350'},{'title':'현대차그룹 데이터 플라이휠','url':'https://www.hyundaimotorgroup.com/ko/news/hyundai-motor-group-atria-ai-data-flywheel-seoul'}]}

@app.put('/api/strategy/scenario')
def update_scenario(body:ScenarioInput,db:Session=Depends(get_db),u:User=Depends(private_user)):
    s=db.get(BusinessScenario,u.id)
    if s is None:
        s=BusinessScenario(user_id=u.id);db.add(s)
    for key,value in body.model_dump().items():setattr(s,key,value)
    s.updated_at=now();db.commit()
    return scenario_view(s)

@app.put('/api/strategy/risks/{code}')
def update_risk(code:str,body:RiskInput,db:Session=Depends(get_db),u:User=Depends(private_user)):
    if code not in {r['code'] for r in INVESTOR_RISKS}:raise HTTPException(404,'위험 항목 없음')
    s=db.scalar(select(RiskEvidence).where(RiskEvidence.user_id==u.id,RiskEvidence.risk_code==code))
    if s is None:
        s=RiskEvidence(user_id=u.id,risk_code=code);db.add(s)
    s.state=body.state;s.note=body.note;s.updated_at=now();db.commit()
    return {'code':code,'state':s.state,'note':s.note}

@app.get('/api/strategy/pilots')
def get_pilots(db:Session=Depends(get_db),u:User=Depends(private_user)):
    a=db.scalars(select(PilotTrial).where(PilotTrial.user_id==u.id).order_by(PilotTrial.id.desc())).all()
    return {'records':[{'id':r.id,'mode':r.mode,'label':r.label,'inspected':r.inspected,'accepted':r.accepted,'duplicate_count':r.duplicate_count,'reviewer_minutes':r.reviewer_minutes,'no_intervention_accepted':r.no_intervention_accepted,'evidence_note':r.evidence_note,'recorded_at':r.recorded_at} for r in a],'summary':pilots_view(a)}

@app.post('/api/strategy/pilots',status_code=201)
def create_pilot(body:PilotInput,db:Session=Depends(get_db),u:User=Depends(private_user)):
    if body.accepted>body.inspected or body.duplicate_count>body.inspected or body.accepted+body.duplicate_count>body.inspected or body.no_intervention_accepted>body.accepted:raise HTTPException(422,'건수 입력값 검증 실패')
    row=PilotTrial(user_id=u.id,recorded_at=now(),**body.model_dump());db.add(row);db.commit()
    return {'id':row.id,'ok':True}

@app.delete('/api/strategy/pilots/{pilot_id}')
def remove_pilot(pilot_id:int,db:Session=Depends(get_db),u:User=Depends(private_user)):
    row=db.scalar(select(PilotTrial).where(PilotTrial.user_id==u.id,PilotTrial.id==pilot_id))
    if row is None:raise HTTPException(404,'검수 기록 없음')
    db.delete(row);db.commit()
    return {'ok':True}

app.mount('/static',StaticFiles(directory=str(STATIC)),name='static')
