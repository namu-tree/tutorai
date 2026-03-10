# TutorAI (A2A Math Item Generator)

## 실행 방법

### 1. 환경 준비

- **Python**: 3.11 권장
- **Redis**: 로컬에서 실행 중이어야 함 (기본: `redis://localhost:6379/0`)
- **환경 변수**: 프로젝트 루트에 `.env` 파일 (이미 있음)
  - `OPENAI_API_KEY`: OpenAI API 키
  - `OPENAI_MODEL`: 사용할 모델 (예: `gpt-4o-mini`)
  - (선택) `REDIS_URL`: Redis URL (기본값: `redis://localhost:6379/0`)

### 2. 의존성 설치

프로젝트 **루트**에서:

```bash
pip install -r backend/requirements.txt
```

### 3. Redis 실행 (WSL 권장)

**WSL(Ubuntu 등)에서 Redis 설치 및 실행:**

```bash
# WSL 터미널에서
sudo apt update
sudo apt install redis-server -y

# Redis 서버 실행 (포그라운드, 터미널 하나 사용)
redis-server
```

다른 터미널에서 앱을 실행할 때는 Redis 터미널은 그대로 두고, Windows에서 접속할 때는 `localhost:6379`로 접속하면 WSL의 Redis에 연결됩니다.

**백그라운드로 실행하고 싶다면:**

```bash
# WSL에서 Redis를 서비스로 실행
sudo service redis-server start

# 상태 확인
sudo service redis-server status
```

(대안: Docker 사용 시 `docker run -d -p 6379:6379 redis:alpine`)

**전체를 WSL에서 실행할 때:**  
WSL 터미널에서 Redis 설치·실행 후, 같은 WSL 안에서 프로젝트 폴더로 이동해 `pip install`, `uvicorn`, `python -m workers...` 를 실행하면 됩니다. Windows 브라우저에서 `http://localhost:8000` 으로 접속 가능합니다.

### 4. API 서버 실행

프로젝트 **루트**에서:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- 접속: http://localhost:8000
- API 문서: http://localhost:8000/docs

### 5. 워커 실행 (세션/문제 생성용)

API와 **별도 터미널**에서 각각 실행:

**오케스트레이터 워커** (세션 이벤트 처리):

```bash
python -m workers.orchestrator_worker
```

**에이전트 워커** (문제 생성/평가 등):

```bash
python -m workers.agent_worker
```

---

## 실행 순서 요약

1. Redis 실행
2. 터미널 1: `uvicorn main:app --reload --port 8000`
3. 터미널 2: `python -m workers.orchestrator_worker`
4. 터미널 3: `python -m workers.agent_worker`

이후 브라우저에서 http://localhost:8000/docs 로 API를 사용할 수 있습니다.

---

## 백엔드 전용 앱 (선택)

`backend/` 폴더의 FastAPI 앱(헬스체크, DB 테스트 등)만 실행하려면:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

- 헬스: http://localhost:8001/health
- DB 테스트 등: `.env`에 `DATABASE_URL`, `OPENAI_API_KEY` 설정 필요
