# RoadChange Insight — Full-stack MVP

> Road-change location intelligence for drive-log discovery, human review and structured data export.
>
> **현대 HINT 사업모델 실습을 위한 독립 개발 프로토타입이며 현대자동차·기아·현대오토에버 공식 제품이 아닙니다.**

## 가장 쉬운 실행 방법 (Windows)

1. Python 3.10 이상을 설치합니다.
2. ZIP 압축을 해제합니다.
3. 폴더 안의 `start_windows.bat`를 더블클릭합니다. 최초 설치에서는 패키지 다운로드를 위해 인터넷 연결이 필요합니다.
4. 브라우저에서 **http://127.0.0.1:8000** 을 엽니다.
5. `실습용 데모 계정 자동 생성`을 눌러 바로 탐색하거나 이메일/비밀번호로 회원가입합니다.

Mac/Linux:

```bash
bash start_mac_linux.sh
# http://127.0.0.1:8000
```

이미 Python 의존성이 있는 환경에서는:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API 문서: **http://127.0.0.1:8000/docs**

## 실제로 동작하는 기능

- 계정 생성·로그인·로그아웃, **PBKDF2 해시 비밀번호**와 HttpOnly 세션 쿠키
- SQLite 로컬 영구 저장, 계정별 데이터 격리; `DATABASE_URL` 사용 시 **Neon PostgreSQL** 지원
- 도로 변경 지점 등록, 관측 시점·위치·변경 유형 기록
- **GPS 좌표와 시각 기반 규칙 매칭** (Haversine 거리, 관측 이후 기간, 동일 주행 클립 중복 후보 표시)
- 검수 후보 목록, **재생 가능한 합성 MP4 영상**, 직접 MP4 첨부 (로컬 서버 모드)
- 검수자 유효·보류·제외 판정과 판정 사유의 DB 이력 기록
- 최신 탐색 실행 기준 **검수 확정 후보만 CSV/JSON으로 출력**
- 샘플 주행 GPS CSV 가져오기, 감사 이력 표시
- AS-IS / TO-BE 비교와 프로젝트 한계 안내

## 빠른 시연 동선

1. 데모 계정 자동 생성 → 합성 변경점/주행 로그 불러옴
2. **도로 변경 탐색** → `광주 테스트구간 A` 선택
3. **주행 로그 매칭** → 반경/기간 확인 후 `후보 장면 검색 실행`
4. **영상 검수** → 동영상을 재생하고 `유효` 선택 → 검수 사유 3자 이상 → 저장
5. **데이터 내보내기** → CSV/JSON 내려받기
6. 브라우저를 닫았다 다시 열어도 세션·기록이 유지되는지 확인

## 데이터 모델

| 테이블 | 역할 |
|---|---|
| users, login_sessions | 계정·해시된 비밀번호·서버 세션 |
| road_changes | 관측 지점/유형/시각 및 반경 |
| drive_clips, gps_points | 로그 메타데이터와 위치별 기록 |
| match_runs, candidates | 매칭 실행/후보/중복 표시/검수 판정 |
| audit_logs | 로그인·변경·매칭·검수·출력 이력 |

매칭 점수는 거리·시간으로 계산되는 **탐색 우선순위 점수**입니다. 자율주행 모델의 신뢰도나 AI 확률이 아닙니다.

### CSV 입력 예시

`demo_data/sample_gps.csv` 참조

```
clip_code,trip_id,sampled_at,latitude,longitude
CUSTOM-001,RUN-USER-001,2026-11-09T00:00:00Z,35.1601,126.8516
```

지점 관측 이후 촬영된 클립만 매칭됩니다. 관측 시점은 **변경 발생 시점의 확정치가 아닙니다.** 또한 지도 화면은 가상 위치를 설명하는 개략도이며 **실제 지도 타일 또는 실제 도로 형상이 아닙니다.**

## 개발 및 테스트

```bash
python -m pip install -r requirements.txt
python -m pip install pytest httpx
python -m pytest -q
```

| 부분 | 기술 |
|---|---|
| Frontend | HTML / CSS / JavaScript, 반응형, 라이브러리 없이 동작 |
| Backend | Python + FastAPI |
| Database | SQLAlchemy + SQLite / Neon PostgreSQL (psycopg) |
| Matching | WGS84 GPS × UTC timestamps / Haversine |
| Video | MP4 (기본 3개 합성 영상 포함) |
| Runtime | 로컬 PC 서버, 필요 시 별도 클라우드 배포 |

## Neon 설정 (선택사항)

Neon 프로젝트의 **pooled connection string**을 복사해 `DATABASE_URL` 환경변수로 지정합니다.

```bash
# 네트워크 연결·Neon 접속 권한 및 psycopg 패키지 필요
export DATABASE_URL='postgresql://USER:PASSWORD@HOST/DB?sslmode=require'
export COOKIE_SECURE=true
export ENABLE_DEMO=false
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`DATABASE_URL`을 설정하지 않으면 `data/roadchange.sqlite3` 파일에 저장됩니다. 데이터베이스 비밀번호는 소스 코드에 입력하거나 GitHub에 올리지 마세요.

## 배포 관련 한계와 안전

- **외부 공개 배포는 아직 하지 않았습니다.** 현재는 로컬에서 실행 가능한 프로젝트입니다.
- Vercel 같은 서버리스 플랫폼에서 `data/uploads/` 로컬 디스크 저장은 영속적이지 않습니다. 실제 업로드는 S3/Blob Storage 같은 영구 객체 스토리지로 별도 교체해야 합니다.
- 인터넷에 공개할 때는 HTTPS, 쿠키 `COOKIE_SECURE=true`, `ENABLE_DEMO=false`, 데이터 접근 통제/백업, CSRF 보호, 전송/저장 암호화, 개인정보 처리 방침, 업로드 악성파일 검증 등을 강화하세요.
- 합성 영상에는 실제 사람·차량·도로가 존재하지 않습니다. 실제 자율주행 로그에는 개인위치정보와 민감한 운행정보가 들어갈 수 있으므로 업로드 전에 법적 권한과 비식별화를 확인하세요.
- 현재 서비스는 지도 변경 정보를 직접 AI로 식별하거나 운전 안전성을 판단하지 않습니다. 실제 지도 변경 기술과 자율주행 모델 학습 파이프라인 연계는 추후 개발 단계입니다.
- 화면은 현대/기아의 모빌리티 디자인 분위기에서 영감을 받은 **독립 디자인**이며 공식 로고·브랜드 요소를 사용하지 않았습니다.

## 프로젝트 구조

```
RoadChange_Insight/
├── app/
│   ├── main.py         # FastAPI routes (auth / maps / match / review / export)
│   ├── db.py           # SQLAlchemy models & database connection
│   ├── matching.py     # distance/time matching logic
│   ├── seed.py         # fictional road-change & GPS data
│   └── static/
│       ├── index.html  # frontend entry
│       ├── styles.css  # responsive UI
│       ├── app.js      # page navigation & API calls
│       └── media/      # synthetic demo videos
├── demo_data/sample_gps.csv
├── data/                # sqlite and optional uploads (Git ignored)
├── tests/test_api.py
├── requirements.txt
├── start_windows.bat
└── start_mac_linux.sh
```
