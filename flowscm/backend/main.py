"""FlowSCM demonstration API. Same-origin web application with SQLite persistence."""
from __future__ import annotations
import csv
import io
import json
import os
import re
import sqlite3
import time
from datetime import date
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import db as store
from .forecast import next_month, forecast

ROOT = Path(__file__).resolve().parent.parent
_schema_ready = False

def ensure_schema():
    global _schema_ready
    if not _schema_ready:
        store.setup()
        _schema_ready = True

@asynccontextmanager
async def lifespan(application):
    ensure_schema()
    yield

app = FastAPI(title='FlowSCM', version='2.0.0', docs_url='/api/docs', redoc_url=None, lifespan=lifespan)
LOGINS: dict[str,list[float]]={}

@app.middleware('http')
async def provision_schema(request: Request, call_next):
    # FastAPI lifespan is not guaranteed on serverless deployments.
    if not _schema_ready:
        try:
            ensure_schema()
        except Exception:
            return JSONResponse({'detail':'데이터베이스 설정을 확인해 주세요.'}, status_code=503)
    return await call_next(request)


def same_origin(request: Request):
    # SameSite strict cookies plus Origin verification on every state change.
    origin = request.headers.get('origin')
    if origin:
        from urllib.parse import urlparse
        o=urlparse(origin)
        host=request.headers.get('host','')
        if o.netloc != host or o.scheme not in ('http','https'):
            raise HTTPException(403,'교차 출처 요청은 허용되지 않습니다.')


def current_user(token: Annotated[str | None, Cookie(alias=store.COOKIE_NAME)] = None):
    user = store.user_from_token(token)
    if not user:
        raise HTTPException(401,'로그인이 필요합니다.')
    return user


def bad_request(message, status=422):
    raise HTTPException(status_code=status, detail=message)

class Signup(BaseModel):
    name: str = Field(min_length=1,max_length=40)
    email: str = Field(min_length=5,max_length=254)
    password: str = Field(min_length=8,max_length=128)

class Login(BaseModel):
    email: str
    password: str

class RecordIn(BaseModel):
    car_model: str = Field(min_length=1,max_length=60)
    period: str
    sales: int = Field(ge=0,le=10_000_000)
    dealer_orders: int = Field(ge=0,le=10_000_000)

class BulkRecords(BaseModel):
    rows: list[RecordIn] = Field(min_length=1,max_length=2000)

class SettingsIn(BaseModel):
    max_gap_pct: float = Field(ge=0,le=100)
    auto_approve: bool

class RunIn(BaseModel):
    car_model: str
    method: Literal['weighted','trend'] = 'weighted'
    confirmed_orders: int = Field(ge=1,le=10_000_000)
    capacity_limit: int | None = Field(default=None,ge=1,le=10_000_000)
    supply_risk: bool = False

class ReviewIn(BaseModel):
    action: Literal['approve','request_changes']
    note: str = Field(min_length=5,max_length=500)
    approved_units: int | None = Field(default=None,ge=1,le=10_000_000)


def valid_record(r):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',r.period):
        bad_request('월은 YYYY-MM 형식이어야 합니다.')
    if not r.car_model.strip():
        bad_request('차종을 입력해 주세요.')

@app.post('/api/auth/signup')
def signup(data: Signup, request: Request, response: Response):
    same_origin(request)
    email=data.email.strip().lower()
    if not store.validate_email(email):bad_request('올바른 이메일 주소를 입력해 주세요.')
    with store.connect() as conn:
        try:
            c=conn.execute('INSERT INTO users(email,name,password_hash,created_at) VALUES (?,?,?,?)', (email,data.name.strip(),store.hash_password(data.password),store.utcnow()))
            uid=c.lastrowid
            conn.execute('INSERT INTO settings(user_id,max_gap_pct,auto_approve) VALUES (?,?,?)', (uid,10.0,1))
            raw=store.create_session(conn,uid)
            store.write_audit(conn,uid,'signup','계정 생성')
        except (sqlite3.IntegrityError, store.UniqueViolation):
            bad_request('이미 등록된 이메일입니다.',409)
    response.set_cookie(store.COOKIE_NAME,raw,max_age=7*86400,httponly=True,samesite='strict',secure=store.COOKIE_SECURE,path='/')
    return {'user':{'id':uid,'name':data.name.strip(),'email':email}}

@app.post('/api/auth/login')
def login(data: Login, request: Request, response: Response):
    same_origin(request)
    email=data.email.strip().lower()
    key=f'{request.client.host if request.client else "none"}:{email}'
    now=time.monotonic()
    LOGINS[key]=[t for t in LOGINS.get(key,[]) if now-t<900]
    if len(LOGINS[key])>=8:
        raise HTTPException(429,'로그인 시도가 많습니다. 15분 후 다시 시도해 주세요.')
    with store.connect() as conn:
        row=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if not row or not store.verify_password(data.password,row['password_hash']):
            LOGINS[key].append(now)
            raise HTTPException(401,'이메일 또는 비밀번호가 올바르지 않습니다.')
        LOGINS.pop(key,None)
        raw=store.create_session(conn,row['id'])
        store.write_audit(conn,row['id'],'login','로그인')
    response.set_cookie(store.COOKIE_NAME,raw,max_age=7*86400,httponly=True,samesite='strict',secure=store.COOKIE_SECURE,path='/')
    return {'user':{'id':row['id'],'name':row['name'],'email':row['email']}}

@app.post('/api/auth/logout')
def logout(request: Request,response: Response,user=Depends(current_user),token: str|None=Cookie(default=None,alias=store.COOKIE_NAME)):
    same_origin(request)
    with store.connect() as conn:
        conn.execute('DELETE FROM sessions WHERE token_hash=?',(store.hash_token(token),))
        store.write_audit(conn,user['id'],'logout','로그아웃')
    response.delete_cookie(store.COOKIE_NAME,path='/')
    return {'ok':True}

@app.get('/api/me')
def me(user=Depends(current_user)):
    return {'user':user}

@app.get('/api/records')
def records(user=Depends(current_user)):
    with store.connect() as conn:
        rows=conn.execute('SELECT id,car_model,period,sales,dealer_orders FROM records WHERE user_id=? ORDER BY car_model,period DESC',(user['id'],)).fetchall()
    return {'records':[dict(x) for x in rows]}

@app.post('/api/records')
def create_record(data:RecordIn,request:Request,user=Depends(current_user)):
    same_origin(request)
    valid_record(data)
    with store.connect() as conn:
        conn.execute('''INSERT INTO records(user_id,car_model,period,sales,dealer_orders,created_at) VALUES(?,?,?,?,?,?)
            ON CONFLICT(user_id,car_model,period) DO UPDATE SET sales=excluded.sales,dealer_orders=excluded.dealer_orders''',
            (user['id'],data.car_model.strip(),data.period,data.sales,data.dealer_orders,store.utcnow()))
        store.write_audit(conn,user['id'],'record_saved',f'{data.period} / {data.car_model[:35]} / {data.sales} / {data.dealer_orders}')
    return {'ok':True}

@app.put('/api/records/{record_id}')
def update_record(record_id:int,data:RecordIn,request:Request,user=Depends(current_user)):
    same_origin(request)
    valid_record(data)
    with store.connect() as conn:
        try:
            cur=conn.execute('''UPDATE records SET car_model=?,period=?,sales=?,dealer_orders=?
                WHERE user_id=? AND id=?''', (data.car_model.strip(),data.period,data.sales,data.dealer_orders,user['id'],record_id))
        except (sqlite3.IntegrityError, store.UniqueViolation):
            bad_request('해당 차종·월의 기록이 이미 있습니다.',409)
        if cur.rowcount<1:bad_request('수정할 데이터를 찾을 수 없습니다.',404)
        store.write_audit(conn,user['id'],'record_saved',f'데이터 #{record_id} 수정 {data.period} / {data.car_model[:35]}')
    return {'ok':True}

@app.post('/api/records/bulk')
def bulk(data:BulkRecords,request:Request,user=Depends(current_user)):
    same_origin(request)
    for row in data.rows:valid_record(row)
    with store.connect() as conn:
        for row in data.rows:
            conn.execute('''INSERT INTO records(user_id,car_model,period,sales,dealer_orders,created_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(user_id,car_model,period) DO UPDATE SET sales=excluded.sales,dealer_orders=excluded.dealer_orders''',
                (user['id'],row.car_model.strip(),row.period,row.sales,row.dealer_orders,store.utcnow()))
        store.write_audit(conn,user['id'],'records_imported',f'{len(data.rows)}개 데이터 등록/갱신')
    return {'ok':True,'count':len(data.rows)}

@app.delete('/api/records/{record_id}')
def delete_record(record_id:int,request:Request,user=Depends(current_user)):
    same_origin(request)
    with store.connect() as conn:
        cur=conn.execute('DELETE FROM records WHERE user_id=? AND id=?',(user['id'],record_id))
        if cur.rowcount<1:bad_request('데이터를 찾을 수 없습니다.',404)
        store.write_audit(conn,user['id'],'record_deleted',f'데이터 #{record_id} 삭제')
    return {'ok':True}

@app.get('/api/records/export.csv')
def records_export(user=Depends(current_user)):
    with store.connect() as conn:
        rows=conn.execute('SELECT car_model,period,sales,dealer_orders FROM records WHERE user_id=? ORDER BY car_model,period',(user['id'],)).fetchall()
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(['car_model','period','sales','dealer_orders'])
    for row in rows:writer.writerow(list(row))
    return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="flowscm_records.csv"'})

@app.get('/api/settings')
def settings(user=Depends(current_user)):
    with store.connect() as conn:
        row=conn.execute('SELECT max_gap_pct,auto_approve FROM settings WHERE user_id=?',(user['id'],)).fetchone()
    return {'max_gap_pct':row['max_gap_pct'],'auto_approve':bool(row['auto_approve'])}

@app.put('/api/settings')
def update_settings(data:SettingsIn,request:Request,user=Depends(current_user)):
    same_origin(request)
    with store.connect() as conn:
        conn.execute('UPDATE settings SET max_gap_pct=?,auto_approve=? WHERE user_id=?',(data.max_gap_pct,int(data.auto_approve),user['id']))
        store.write_audit(conn,user['id'],'settings_changed',f'허용 편차 {data.max_gap_pct}% / 자동 확정 {data.auto_approve}')
    return {'ok':True}

@app.post('/api/plans/run')
def run(data:RunIn,request:Request,user=Depends(current_user)):
    same_origin(request)
    with store.connect() as conn:
        rec=[dict(r) for r in conn.execute('''SELECT car_model,period,sales,dealer_orders FROM records WHERE user_id=? AND car_model=? ORDER BY period''',(user['id'],data.car_model.strip())).fetchall()]
        if len(rec)<3:bad_request('선택한 차종의 최근 3개월 이상 자료를 등록해야 합니다.')
        last=rec[-3:]
        for prev,curr in zip(last,last[1:]):
            if next_month(prev['period'])!=curr['period']:
                bad_request('최신 3개월 데이터가 연속되어야 합니다. 누락된 월을 등록해 주세요.')
        predicted,details=forecast(rec,data.method)
        cfg=conn.execute('SELECT max_gap_pct,auto_approve FROM settings WHERE user_id=?',(user['id'],)).fetchone()
        gap_pct=round(abs(predicted-data.confirmed_orders)/data.confirmed_orders*100,2)
        reasons=[]
        if gap_pct>cfg['max_gap_pct']:reasons.append(f'예측·수주 편차 {gap_pct:.2f}% > 기준 {cfg["max_gap_pct"]:g}%')
        if data.capacity_limit is not None and predicted>data.capacity_limit:reasons.append('생산능력 참고 상한 초과')
        if data.supply_risk:reasons.append('공급 위험 표시')
        if not cfg['auto_approve']:reasons.append('자동 확정 설정 해제')
        status='pending_review' if reasons else 'auto_approved'
        reason=' / '.join(reasons) if reasons else '기준 충족 · 자동 확정(교육용 규칙)'
        approved_units=predicted if status=='auto_approved' else None
        now=store.utcnow()
        cur=conn.execute('''INSERT INTO plans(user_id,car_model,target_period,method,forecast_units,confirmed_orders,gap_pct,
            threshold_pct,capacity_limit,supply_risk,status,reason,approved_units,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (user['id'],data.car_model.strip(),next_month(rec[-1]['period']),data.method,predicted,data.confirmed_orders,gap_pct,
            cfg['max_gap_pct'],data.capacity_limit,int(data.supply_risk),status,reason,approved_units,now))
        store.write_audit(conn,user['id'],'forecast_run',f'계획 #{cur.lastrowid} / {status} / {reason}')
        result=conn.execute('SELECT * FROM plans WHERE id=?',(cur.lastrowid,)).fetchone()
    return {'plan':dict(result),'model_detail':details,'important_note':'계산값은 통계 기반 시연 결과이며 미래 실판매량 또는 실제 예측 정확도 성과가 아닙니다.'}

@app.get('/api/plans')
def plans(user=Depends(current_user)):
    with store.connect() as conn:
        rows=conn.execute('SELECT * FROM plans WHERE user_id=? ORDER BY id DESC LIMIT 300',(user['id'],)).fetchall()
    return {'plans':[dict(r) for r in rows]}

@app.post('/api/plans/{plan_id}/review')
def review(plan_id:int,data:ReviewIn,request:Request,user=Depends(current_user)):
    same_origin(request)
    with store.connect() as conn:
        plan=conn.execute('SELECT * FROM plans WHERE id=? AND user_id=?',(plan_id,user['id'])).fetchone()
        if not plan:bad_request('계획을 찾을 수 없습니다.',404)
        if plan['status']!='pending_review':bad_request('검토 대기 중인 계획만 처리할 수 있습니다.')
        if data.action=='approve':
            units=data.approved_units or plan['forecast_units']
            status='manually_approved'
        else:
            units=None
            status='revision_requested'
        conn.execute('UPDATE plans SET status=?,review_note=?,approved_units=?,reviewed_at=? WHERE id=? AND user_id=?',
            (status,data.note,units,store.utcnow(),plan_id,user['id']))
        store.write_audit(conn,user['id'],'plan_review',f'계획 #{plan_id} / {status} / 사유 {data.note[:80]}')
        row=conn.execute('SELECT * FROM plans WHERE id=?',(plan_id,)).fetchone()
    return {'plan':dict(row)}

@app.get('/api/plans/export.csv')
def plans_export(user=Depends(current_user)):
    with store.connect() as conn:
        rows=conn.execute('''SELECT target_period,car_model,forecast_units,confirmed_orders,gap_pct,status,approved_units,reason,review_note
                FROM plans WHERE user_id=? AND status IN ('auto_approved','manually_approved') ORDER BY id DESC''',(user['id'],)).fetchall()
    output=io.StringIO();w=csv.writer(output)
    w.writerow(['target_period','car_model','forecast_units','confirmed_orders','gap_pct','status','approved_units','reason','review_note'])
    for row in rows:w.writerow(list(row))
    return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="flowscm_approved_plans.csv"'})

@app.get('/api/audit')
def audit(user=Depends(current_user)):
    with store.connect() as conn:
        rows=conn.execute('SELECT event,detail,created_at FROM audit WHERE user_id=? ORDER BY id DESC LIMIT 80',(user['id'],)).fetchall()
    return {'audit':[dict(r) for r in rows]}

@app.get('/api/health')
def health():
    try:
        ensure_schema()
    except Exception:
        raise HTTPException(503,'데이터베이스 연결을 확인해 주세요.')
    return {'status':'ok','db':'postgres' if os.getenv('DATABASE_URL') else 'sqlite'}

# Serve the responsive SPA under the same origin as API, to keep auth cookie private.
app.mount('/assets',StaticFiles(directory=str(ROOT/'frontend')),name='assets')

@app.get('/')
def index():return FileResponse(str(ROOT/'frontend'/'index.html'))

@app.get('/{path:path}')
def spa(path:str):
    if path.startswith('api/'):
        raise HTTPException(404,'API를 찾을 수 없습니다.')
    return FileResponse(str(ROOT/'frontend'/'index.html'))
