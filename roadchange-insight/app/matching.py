"""Explicit, testable space-time matching; no AI inference or road-change time claims."""
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

def dt(value):
    out = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return out.replace(tzinfo=timezone.utc) if out.tzinfo is None else out.astimezone(timezone.utc)

def haversine_m(a_lat, a_lon, b_lat, b_lon):
    rad = 6371000
    lat1, lat2 = radians(a_lat), radians(b_lat)
    dlat = lat2-lat1; dlon = radians(b_lon-a_lon)
    return 2*rad*asin(min(1,sqrt(sin(dlat/2)**2+cos(lat1)*cos(lat2)*sin(dlon/2)**2)))

def match_clips(change, clips, points_by_clip, radius_m=550, window_days=7):
    """Return nearest post-observation sample for clips inside radius/window.
    Observed_at is first observation, NOT verified onset time; analyst must review.
    """
    observed=dt(change.observed_at)
    eligible=[]
    for clip in clips:
        matches=[]
        for p in points_by_clip.get(clip.id,[]):
            t=dt(p.sampled_at)
            since=(t-observed).total_seconds()
            if not 0 <= since <= window_days*86400: continue
            distance=haversine_m(change.latitude,change.longitude,p.latitude,p.longitude)
            if distance <= radius_m:
                matches.append((distance,t))
        if matches:
            dist,t=min(matches,key=lambda v:v[0])
            days=(t-observed).total_seconds()/86400
            score=round(max(1, 100-(dist/max(radius_m,1))*63-(days/max(window_days,1))*18),1)
            eligible.append({'clip':clip,'distance_m':round(dist,1),'matched_at':t.isoformat(), 'score':score,'is_duplicate':False})
    eligible.sort(key=lambda v:-v['score'])
    for idx, entry in enumerate(eligible):
        for prev in eligible[:idx]:
            same_trip=entry['clip'].trip_id == prev['clip'].trip_id
            seconds=abs((dt(entry['clip'].start_at)-dt(prev['clip'].start_at)).total_seconds())
            if same_trip and seconds < 180:
                entry['is_duplicate']=True
                break
    return eligible
