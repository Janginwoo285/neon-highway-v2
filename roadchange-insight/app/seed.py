"""Fictional demo locations and synthetic drive logs; not real vehicle telematics."""
from datetime import datetime,timedelta,timezone
from .db import RoadChange,DriveClip,GpsPoint

def seed_demo(db,uid):
    t0=(datetime.now(timezone.utc)-timedelta(days=5)).replace(hour=9,minute=0,second=0,microsecond=0)
    events=[
        ('RC-001','광주 테스트구간 A · 임시 차선 이동','임시 차선',35.1601,126.8516,t0,620,'도로 공사 후 임시 차선 이동 가능성을 가정한 가상 변경점'),
        ('RC-002','광주 테스트구간 B · 차로 폐쇄','차로 폐쇄',35.1566,126.8562,t0+timedelta(days=1),560,'차로 폐쇄를 가정한 가상 구간'),
        ('RC-003','광주 테스트구간 C · 진입로 변경','진입로 변경',35.1635,126.8447,t0+timedelta(days=2),480,'진입로 변경을 가정한 가상 구간'),
    ]
    for code,name,kind,lat,lon,obs,radius,desc in events:
        db.add(RoadChange(user_id=uid,code=code,name=name,kind=kind,latitude=lat,longitude=lon,observed_at=obs.isoformat(),radius_m=radius,description=desc,source='synthetic-demo'))
    db.flush()
    clips=[
        ('DV-105','RUN-A01',0,35.1609,126.8519,10,'demo-road-a.mp4'),
        ('DV-106','RUN-A02',0,35.1588,126.8510,12,'demo-road-a.mp4'),
        ('DV-107','RUN-A01',0,35.1604,126.8524,10,'demo-road-a.mp4'),
        ('DV-108','RUN-A03',0,35.1616,126.8520,16,'demo-road-a.mp4'),
        ('DV-109','RUN-B04',1,35.1569,126.8561,21,'demo-road-b.mp4'),
        ('DV-110','RUN-B05',1,35.1557,126.8570,27,'demo-road-b.mp4'),
        ('DV-111','RUN-C08',2,35.1639,126.8456,25,'demo-road-c.mp4'),
        ('DV-112','RUN-C09',2,35.1632,126.8441,26,'demo-road-c.mp4'),
        ('DV-113','RUN-OFF',0,35.1910,126.9120,18,'demo-road-a.mp4'),
        ('DV-114','RUN-BEFORE',0,35.1600,126.8515,-12,'demo-road-a.mp4'),
    ]
    for i,(code,trip,idx,lat,lon,hours,video) in enumerate(clips):
        obs=events[idx][5]
        when=obs+timedelta(hours=hours, seconds=125 if code=='DV-107' else 0)
        new=DriveClip(user_id=uid,code=code,trip_id=trip,start_at=when.isoformat(),end_at=(when+timedelta(seconds=45)).isoformat(),video_path=video,source='synthetic-demo')
        db.add(new);db.flush()
        for ix in range(5):
            db.add(GpsPoint(clip_id=new.id,sampled_at=(when+timedelta(seconds=ix*8)).isoformat(),latitude=lat+0.0001*(ix-2),longitude=lon+0.00013*(ix-2)))
    db.commit()


def append_synthetic_demo(db, uid, batch_number):
    """Add another fictional batch (2 change points, 8 logs, 40 GPS samples).

    Do not delete or modify any existing per-user records. Caller commits.
    No real fleet or driving data is used.
    """
    import secrets
    t0=(datetime.now(timezone.utc)-timedelta(days=2)).replace(minute=0,second=0,microsecond=0)
    kinds=['임시 차선','차로 폐쇄','진입로 변경','공사 구간']
    created=[]
    for i in range(2):
        code=f"SIM-{secrets.token_hex(4).upper()}"
        lat=35.149 + (batch_number % 6)*0.0016 + i*0.0021
        lon=126.840 + (batch_number % 7)*0.0017 + i*0.0020
        obs=t0+timedelta(hours=i*5)
        kind=kinds[(batch_number+i)%len(kinds)]
        change=RoadChange(
            user_id=uid,code=code,name=f'가상 도로 시나리오 {batch_number+1}-{i+1} · {kind}',
            kind=kind,latitude=lat,longitude=lon,observed_at=obs.isoformat(),
            radius_m=550,description='시연용 무작위 합성 데이터. 실제 도로 상황·주행기록이 아닙니다.',
            source='synthetic-demo'
        )
        db.add(change);db.flush();created.append(change.id)
        for j in range(4):
            # j=1 repeats the same trip to exercise duplicate filtering.
            # j=3 is far away, so the matching UI can exclude it.
            trip=f'{code}-TRIP-{0 if j==1 else j}'
            offset_lat=0.038 if j==3 else [0.00014,0.00026,-0.00030][j]
            offset_lon=0.039 if j==3 else [0.00010,0.00020,-0.00018][j]
            when=obs+timedelta(hours=4+j,seconds=j*80)
            clip=DriveClip(
                user_id=uid,code=f'DEMO-{secrets.token_hex(4).upper()}',trip_id=trip,
                start_at=when.isoformat(),end_at=(when+timedelta(seconds=45)).isoformat(),
                video_path=['demo-road-a.mp4','demo-road-b.mp4','demo-road-c.mp4'][i%3],
                source='synthetic-demo'
            )
            db.add(clip);db.flush()
            for k in range(5):
                db.add(GpsPoint(clip_id=clip.id, sampled_at=(when+timedelta(seconds=8*k)).isoformat(),
                    latitude=lat+offset_lat+(k-2)*0.00006,
                    longitude=lon+offset_lon+(k-2)*0.00007))
    db.flush()
    return {'changes_added':2,'clips_added':8,'gps_points_added':40,'created_change_ids':created}
