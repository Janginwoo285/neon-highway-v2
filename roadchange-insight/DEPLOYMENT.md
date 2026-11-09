# RoadChange Insight — 무료 클라우드 배포

**실제 현대오토에버·현대차·기아 제품이 아닌 독립 교육용 MVP입니다.**

## 권장 구성

- 앱 + FastAPI: Railway Free 사용 크레딧 또는 Render 무료 Web Service
- 데이터베이스: 별도 Neon Free PostgreSQL 프로젝트
- GitHub: 소스 저장, 커밋 시 자동 배포
- 합성 주행 영상: `app/static/media/`에 포함
- 계정, 매칭 결과, 검수 이력: Neon PostgreSQL에 영구 저장

## Railway

1. GitHub `Janginwoo285/neon-highway-v2` 저장소의 `/roadchange-insight` 폴더를 서비스 루트 디렉터리로 지정합니다.
2. `requirements.txt`로 파이썬 패키지를 설치합니다.
3. 시작 명령: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. 헬스체크: `/api/health`
5. 환경변수: `DATABASE_URL` (Neon 비밀 연결문자열; 깃허브에 절대 업로드하지 말 것), `COOKIE_SECURE=true`, `ENABLE_DEMO=true`, `DISABLE_VIDEO_UPLOADS=true`.
6. 도메인 생성 후 `https://<service>.up.railway.app/` 접속 및 `/api/health` 테스트.

## 무료 플랜 제한

Railway 무료 플랜은 사용량 크레딧 한도 내에서만 실행됩니다. Render 무료 Web Service는 트래픽이 없으면 잠들고 재시작·재배포 때 로컬 파일을 잃습니다. 따라서 SQLite가 아니라 Neon을 연결해야 계정과 기록이 남습니다. 업로드 MP4는 영구 스토리지를 아직 구현하지 않아 외부 배포에서는 비활성화했습니다. CSV/GPS 메타데이터 입력과 검수·내보내기는 정상 동작합니다.

## 안전

- 로그인 쿠키 HTTPS 전용, 비밀번호 PBKDF2 해시. 데모 계정 생성 가능.
- 가입한 이용자별 계정·기록은 분리되나 이메일 인증 및 사용량 제한 등 상용 보안 기능은 구현 전입니다.
- 실제 개인정보/차량 위치/주행 영상은 업로드하지 마세요.
- 무료 크레딧 초과 또는 서비스 비활성화 때 접속이 중단될 수 있습니다.
