"""Integration tests for auth isolation, GPS matching, review workflow, exports."""
import os
import tempfile
from pathlib import Path
os.environ['DATABASE_URL']=f"sqlite:///{Path(tempfile.mkdtemp(prefix='roadchange_tests_')) / 'test.sqlite3'}"
os.environ['ENABLE_DEMO']='true'
os.environ['COOKIE_SECURE']='false'
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal,User


def test_health_and_authentication_required():
    c=TestClient(app)
    assert c.get('/api/health').json()['ok']
    assert c.get('/').status_code==200
    assert c.get('/static/app.js').status_code==200
    assert c.get('/api/auth/me').json()['authenticated'] is False
    assert c.get('/api/changes').status_code==401
    assert c.get('/api/candidates').status_code==401


def test_demo_full_workflow_and_persistent_login():
    c=TestClient(app)
    created=c.post('/api/auth/demo',json={})
    assert created.status_code==200, created.text
    assert created.json()['authenticated']
    assert c.get('/api/auth/me').json()['authenticated']
    changes=c.get('/api/changes').json()
    assert len(changes)==3
    clips=c.get('/api/clips').json()
    assert len(clips)==10
    run=c.post('/api/matches/run',json={'change_id':changes[0]['id'],'radius_m':620,'window_days':7})
    assert run.status_code==200,run.text
    assert run.json()['count']>=3,run.json()
    assert run.json()['duplicates']>=1
    candidates=c.get('/api/candidates',params={'change_id':changes[0]['id']}).json()
    assert len(candidates)==run.json()['count']
    assert all(x['distance_m']<=620 for x in candidates)
    assert all(x['source']=='synthetic-demo' for x in candidates)
    dup=next(x for x in candidates if x['is_duplicate'])
    reject=c.post(f"/api/candidates/{dup['id']}/review",json={'status':'accepted','note':'중복 구간도 임의 승인'})
    assert reject.status_code==409
    cand=next(x for x in candidates if not x['is_duplicate'])
    r=c.get(f"/api/clips/{cand['clip_id']}/video")
    assert r.status_code==200 and len(r.content)>1000
    reviewed=c.post(f"/api/candidates/{cand['id']}/review",json={'status':'accepted','note':'차로 변경이 합성 영상에서 확인되었습니다.'})
    assert reviewed.status_code==200,reviewed.text
    assert c.get('/api/candidates').json()[0]['review_status'] in ['accepted','pending']
    exported=c.get('/api/export?format=csv')
    assert exported.status_code==200
    assert cand['clip_code'] in exported.content.decode('utf-8-sig')
    exported_json=c.get('/api/export?format=json').json()
    assert len(exported_json['records'])==1
    assert exported_json['records'][0]['clip_code']==cand['clip_code']
    # Cookie session remains valid across HTTP requests.
    assert c.get('/api/auth/me').json()['authenticated']
    assert c.post('/api/auth/logout',json={}).status_code==200
    assert c.get('/api/auth/me').json()['authenticated'] is False


def test_register_login_storage_and_cross_user_isolation():
    a=TestClient(app);b=TestClient(app)
    reg=a.post('/api/auth/register',json={'name':'테스트 담당자','email':'usera@example.test','password':'SafePassword42'})
    assert reg.status_code==200,reg.text
    user=reg.json()['user']
    with SessionLocal() as db:
        record=db.get(User,user['id'])
        assert record.password_hash!='SafePassword42'
        assert record.password_hash.startswith('pbkdf2_sha256:')
    change=a.post('/api/changes',json={'name':'가상 테스트 구간 추가','kind':'임시 차선','latitude':35.16,'longitude':126.85,'observed_at':'2026-11-04T12:00:00+09:00','radius_m':450,'description':'테스트'} )
    assert change.status_code==201,change.text
    bid=b.post('/api/auth/register',json={'name':'별도 사용자','email':'userb@example.test','password':'StrongPassword123'})
    assert bid.status_code==200
    assert b.get('/api/changes').json()==[]
    assert b.post('/api/matches/run',json={'change_id':change.json()['id'],'radius_m':450,'window_days':7}).status_code==404
    assert b.get('/api/candidates').json()==[]
    a.post('/api/auth/logout',json={})
    assert a.post('/api/auth/login',json={'email':'usera@example.test','password':'SafePassword42'}).status_code==200
    assert len(a.get('/api/changes').json())==1
    assert a.post('/api/auth/login',json={'email':'usera@example.test','password':'incorrect12'}).status_code==401


def test_csv_gps_import_and_validation():
    c=TestClient(app);assert c.post('/api/auth/demo',json={}).status_code==200
    raw='clip_code,trip_id,sampled_at,latitude,longitude\nUSER-1,SESSION-1,2026-11-09T00:00:00Z,35.1601,126.8516\nUSER-1,SESSION-1,2026-11-09T00:00:10Z,35.1602,126.8517\n'
    out=c.post('/api/import/logs',files={'file':('logs.csv',raw.encode(),'text/csv')})
    assert out.status_code==200,out.text
    assert out.json()['clips']==1
    assert out.json()['points']==2
    assert len(c.get('/api/clips').json())==11
    invalid=c.post('/api/import/logs',files={'file':('bad.csv',b'x,y\na,b','text/csv')})
    assert invalid.status_code==422


def test_invalid_or_unauthorized_video_upload():
    c=TestClient(app);assert c.post('/api/auth/demo',json={}).status_code==200
    clip_id=c.get('/api/clips').json()[0]['id']
    assert c.post(f'/api/clips/{clip_id}/video',files={'file':('bad.txt',b'hello','text/plain')}).status_code==400
    assert c.post(f'/api/clips/{clip_id}/video',files={'file':('bad.mp4',b'just text','video/mp4')}).status_code==400
