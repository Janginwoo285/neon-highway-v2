# FlowSCM · Vercel + Neon 배포 버전

기존 현대 HINT 1조 모바일형 FlowSCM의 로그인·수요예측·예외검토·이력 저장 기능을 유지하면서 Vercel과 Neon PostgreSQL을 지원하도록 포팅했습니다. 실제 현대차 시스템과 연결되지 않는 교육용 프로토타입입니다.

## 구성
- `app.py` FastAPI Vercel entrypoint
- `backend/main.py` 로그인, 데이터 등록, 수요예측, 승인, CSV API
- `backend/db.py` Neon PostgreSQL 저장 또는 로컬 SQLite 대체
- `frontend/` 모바일 UI: 현상인식·문제제기·목적·전략·기대효과 및 업무 실습

## 배포
1. GitHub 저장소의 `flowscm` 폴더를 Vercel 프로젝트의 Root Directory로 지정합니다. Framework는 FastAPI, Python Runtime.
2. Neon PostgreSQL 데이터베이스를 생성하고, Vercel Project에 `DATABASE_URL` 환경 변수로 **pooled** PostgreSQL 연결 문자열을 연결합니다. 절대로 깃허브/채팅에 비밀번호 또는 연결 문자열을 올리지 마세요.
3. 환경 변수 `FLOWSCM_COOKIE_SECURE=1`을 설정합니다.
4. Vercel을 Deploy한 뒤 `/api/health`에서 `db:postgres`를 확인하세요. 첫 호출에서 테이블 스키마가 없는 경우 자동 생성됩니다.
5. 로그인, 데이터 등록, 예측, 예외 승인 후 새로고침/재접속 시 데이터가 남는지 검증합니다.

배포가 완료되기 전에는 운영용 사용자 데이터나 실제 개인정보를 입력하지 마세요. 서비스 운영 시 HTTPS, 접근 권한, 개인정보처리방침, DB 백업, 모니터링, 지속 가능한 로그인 시도 제한 등이 필요합니다.

## 로컬 테스트
```bash
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

DATABASE_URL 미지정 시 로컬 SQLite 파일 `data/flowscm.sqlite3`로 동작합니다. Vercel에서는 DATABASE_URL이 없으면 DB 쓰기를 거부합니다.

## 데이터
- `users` 사용자와 비밀번호 해시
- `sessions` 해시된 로그인 토큰
- `records` 판매·딜러 주문 데이터
- `settings` 승인 기준
- `plans` 예측/승인 상태
- `audit` 계정별 변경 이력
