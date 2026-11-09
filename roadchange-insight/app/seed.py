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
