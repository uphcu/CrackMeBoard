# CrackMeBoard — 코드 이해 가이드

> 이 문서는 코드를 처음 보는 사람이 발표할 수 있도록,  
> "왜 이렇게 만들었는지"를 중심으로 설명합니다.

---

## 1. 전체 구조 (어떻게 폴더가 나뉘어 있는가)

```
crackmeboard/
├── app/                    ← Flask 앱 본체
│   ├── __init__.py         ← 앱 생성 + 확장 기능 초기화 (시작점)
│   ├── models.py           ← 데이터베이스 테이블 정의
│   ├── auth/               ← 회원가입, 로그인, 2FA (인증 담당)
│   ├── board/              ← 게시판 CRUD (글쓰기, 읽기, 수정, 삭제)
│   ├── core/               ← 홈페이지, 허니팟 (함정 라우트)
│   └── templates/          ← HTML 템플릿 (화면)
├── requirements.txt        ← 필요한 Python 패키지 목록
├── crackmeboard.service    ← 서버 자동 실행 설정 (systemd)
└── crackmeboard.nginx.conf ← Nginx 웹 서버 설정
```

### 핵심 개념: Blueprint (블루프린트)

Flask에서 **Blueprint**는 기능별로 라우트(URL 경로)를 그룹화하는 방식이에요.

| Blueprint  | URL 접두사  | 담당 기능             |
|-----------|------------|----------------------|
| `core_bp` | `/`        | 홈, 허니팟            |
| `auth_bp` | `/auth`    | 로그인, 회원가입, 2FA |
| `board_bp`| `/board`  | 게시판 CRUD          |

→ `auth_bp.route("/login")`에 등록하면 실제 URL은 `/auth/login`이 됩니다.

---

## 2. 앱 시작 흐름 (`app/__init__.py`)

`create_app()` 함수가 앱을 만들고 모든 초기화를 수행해요:

```
1. Flask 앱 생성
2. 설정 로드 (SECRET_KEY, DB 경로 등)
3. 확장 기능 연결:
   - SQLAlchemy (DB)
   - Flask-Login (세션/로그인 관리)
   - Flask-WTF (CSRF 보호)
   - Flask-Limiter (요청 속도 제한)
4. Blueprint 등록 (auth, board, core)
5. DB 테이블 생성
6. 에러 핸들러 등록 (404, 500)
```

### 여기서 중요한 보안 설정들:

| 설정                         | 역할                                            |
|-----------------------------|------------------------------------------------|
| `SECRET_KEY`                | 세션 암호화 키. 환경변수에서만 읽어옴 (코드에 하드코딩 X) |
| `WTF_CSRF_TIME_LIMIT = 3600` | CSRF 토큰 유효시간 1시간                           |
| `session_protection = "strong"` | 세션 탈취 의심 시 강제 로그아웃                     |
| `default_limits`           | IP당 시간당 50회, 하루 200회 요청 제한              |

---

## 3. 데이터베이스 (`models.py`)

SQLite를 사용하며, **3개의 테이블**이 있어요:

### 3-1. User (사용자)

| 필드            | 타입       | 설명                        |
|----------------|-----------|----------------------------|
| `id`          | Integer   | 기본키 (자동 증가)              |
| `email`       | String    | 이메일 (고유, 인덱스)            |
| `username`    | String    | 사용자명 (고유, 3~50자)         |
| `password_hash`| String   | **비밀번호 해시** (원문 저장 X)   |
| `totp_secret` | String    | 2FA용 비밀키 (32자 랜덤)        |
| `totp_enabled`| Boolean   | 2FA 활성화 여부               |
| `created_at`  | DateTime  | 가입 시각                     |
| `last_login`  | DateTime  | 마지막 로그인 시각               |

**핵심 메서드:**

```python
def set_password(self, password):
    self.password_hash = generate_password_hash(password)
    # 비밀번호를 그대로 저장하지 않고, 해시(일방향 암호화)로 저장
    # 해킹당해도 원문 비밀번호를 알 수 없음

def check_password(self, password):
    return check_password_hash(self.password_hash, password)
    # 입력된 비밀번호를 해시해서 DB의 해시와 비교
```

> **왜 해시인가?** 비밀번호를 평문으로 저장하면 DB가 털렸을 때 모든 비밀번호가 노출됩니다. 해시는 원문을 복구할 수 없는 일방향 함수라서, DB가 유출되어도 비밀번호를 알 수 없어요.

### 3-2. LoginLog (로그인 기록)

| 필드              | 설명                          |
|------------------|------------------------------|
| `user_id`       | 누가 시도했는지 (없는 사용자면 NULL)  |
| `ip_address`    | 어디서 시도했는지                |
| `user_agent`    | 브라우저 정보                    |
| `success`       | 성공/실패                      |
| `failure_reason`| 실패 사유 (wrong_password 등)  |

→ 공격자가 무차별 대입(brute force)을 시도할 때, 이 로그를 통해 추적할 수 있어요.

### 3-3. Post (게시글)

| 필드           | 설명                              |
|---------------|----------------------------------|
| `id`         | 게시글 번호                        |
| `user_id`    | 작성자 (외래키 → users.id)        |
| `title`      | 제목 (최대 200자)                  |
| `content`    | 내용                              |
| `created_at` | 작성 시각                         |
| `updated_at` | 수정 시각 (수정 시 자동 갱신)       |

---

## 4. 인증 시스템 (`auth/routes.py`)

### 4-1. 회원가입 (`/auth/register`)

```
사용자 입력: email, username, password
    ↓
검증:
  - email에 @ 포함? 길이 255 이하?
  - username 3~50자?
  - password 8자 이상?
  - 이미 존재하는 email/username?
    ↓
통과 → 비밀번호 해싱 → DB 저장 → 201 응답
실패 → 에러 메시지 → 400 응답
```

**보안 포인트:**
- **Rate Limit**: IP+사용자명 기준 분당 5회만 가입 시도 가능
  → 봇이 무한 가입 시도를 막음

### 4-2. 로그인 (`/auth/login`)

```
사용자 입력: email, password (+ totp_code if 2FA)
    ↓
1. email로 사용자 찾기
   - 없으면 → "이메일 또는 비밀번호가 올바르지 않습니다" (401)
     ※ "존재하지 않는 이메일입니다"라고 안 함
     → 공격자가 어떤 이메일이 가입되어 있는지 알 수 없게 함 (사용자 나열 공격 방지)

2. 비밀번호 검증 (해시 비교)
   - 틀리면 → 같은 메시지 (401)

3. 2FA 활성화 여부 확인
   - 활성화 → totp_code 검증
   - 틀리면 → "2FA 코드가 올바르지 않습니다" (401)

4. 모두 통과 → 세션 발급 (12시간 유지) → 로그인 성공 (200)
```

**보안 포인트:**
- 실패 메시지가 "이메일 또는 비밀번호가 올바르지 않습니다"로 동일
  → 공격자가 이메일 존재 여부를 알 수 없음
- `remember=True, duration=timedelta(hours=12)` → 세션 12시간 후 자동 만료
- 모든 시도(성공/실패)를 LoginLog에 기록

### 4-3. 2FA (TOTP) (`/auth/2fa/setup`, `/auth/2fa/disable`)

**TOTP란?** Time-based One-Time Password.  
Google Authenticator 같은 앱이 30초마다 새로운 6자리 숫자를 생성하는 방식.

**설정 흐름:**
```
1. GET /auth/2fa/setup
   → totp_secret이 없으면 32자 랜덤 키 생성
   → TOTP URI 생성 → QR 코드로 변환 → 화면에 표시
   
2. 사용자가 앱으로 QR 스캔 → 6자리 코드 입력
   → POST /auth/2fa/setup (code 전송)
   → totp.verify(code)로 검증
   → 통과하면 totp_enabled = True
```

**해제 흐름:**
```
1. POST /auth/2fa/disable (code 전송)
   → totp_enabled 확인
   → totp_secret이 없으면 (비정상 상태) 자동 복구
   → totp.verify(code) 검증
   → 통과하면 totp_enabled = False
```

> **왜 2FA가 필요한가?** 비밀번호가 유출되어도 2FA 코드 없으면 로그인 불가. 2단계 보안.

### 4-4. 허니팟 (Honeypot) (`/auth/honeypot/<path>`)

```python
HONEYPOT_PATHS = ["/admin.php", "/wp-admin", "/phpmyadmin", "/.env", "/api/v1/admin"]
```

**허니팟이란?** 가짜 관리자 페이지 경로.  
공격자가 자동 스캐너로 흔한 admin 경로를 찌를 때:

- **로그 기록**: 누가, 어느 IP에서, 언제 공격했는지 저장
- **404 반환**: "이건 허니팟이다"라고 들키지 않게 그냥 404

→ 공격 탐지용. 실제 관리자 페이지가 아니라 함정.

---

## 5. 게시판 (`board/routes.py`)

### CRUD = Create, Read, Update, Delete

| 기능   | URL                    | 메서드     | 권한            |
|-------|------------------------|----------|----------------|
| 목록   | `/board/`              | GET      | 누구나          |
| 읽기   | `/board/<id>`          | GET      | 누구나          |
| 쓰기   | `/board/new`           | GET/POST | **로그인 필요**  |
| 수정   | `/board/<id>/edit`     | GET/POST | **작성자만**    |
| 삭제   | `/board/<id>/delete`   | POST     | **작성자만**    |

### 5-1. XSS 방지 (`_sanitize_html`)

```python
ALLOWED_TAGS = ["b", "i", "u", "strong", "em", "p", "br", ...]

def _sanitize_html(text):
    return bleach.clean(text, tags=ALLOWED_TAGS, strip=True)
```

**XSS(크로스 사이트 스크립팅)란?**  
공격자가 게시글에 `<script>alert('해킹')</script>` 같은 악성 코드를 심어,  
다른 사용자가 글을 읽을 때 브라우저에서 스크립트가 실행되는 공격.

**방어 방법:**  
`bleach` 라이브러리로 HTML에서 허용된 태그만 남기고, `<script>` 같은 위험한 태그는 제거.

### 5-2. IDOR 방지 (Insecure Direct Object Reference)

```python
# 수정/ 삭제 시:
post = Post.query.get_or_404(post_id)
if post.user_id != current_user.id:
    abort(403)  # 작성자가 아니면 거부
```

**IDOR란?**  
URL에서 게시글 ID를 바꿔가며(`board/1/edit`, `board/2/edit`) 남의 글을 수정하려는 공격.

**방어:** 수정/삭제 요청이 들어오면, 게시글의 작성자 ID와 현재 로그인한 사용자 ID를 비교. 다르면 403 Forbidden.

### 5-3. SQL Injection 방지

```python
Post.query.filter_by(email=email).first()
Post.query.get_or_404(post_id)
```

Flask-SQLAlchemy의 ORM을 사용하면, SQL 쿼리를 직접 문자열로 조립하지 않고  
Python 객체로 다루기 때문에 자동으로 파라미터 바인딩(prepared statement)이 적용됨.  
→ 사용자 입력이 SQL에 직접 들어가지 않아 SQLi 공격을 방어.

---

## 6. 코어 라우트 (`core/routes.py`)

### 허니팟 Catch-All

```python
HONEYPOT_PATHS = [
    "admin.php", "wp-admin", "wp-login.php", "phpmyadmin",
    ".env", ".git/config", "api/v1/admin", ...
]

@core_bp.route("/<path:path>")
def catch_all(path):
    if any(hp in path.lower() for hp in HONEYPOT_PATHS):
        logging.warning(f"HONEYPOT TRIGGERED: /{path} from {request.remote_addr}")
        return abort(404)
    return abort(404)
```

→ 정의되지 않은 **모든 URL**이 여기로 옴.  
그 중에 공격자가 자주 찌르는 경로(`admin.php`, `.env`, `.git/config` 등)가 있으면  
경고 로그를 남기고 404를 반환.

---

## 7. 보안 기능 종합 정리

| 공격 유형       | 방어 방법                          | 코드 위치                  |
|---------------|----------------------------------|--------------------------|
| **비밀번호 유출** | bcrypt 해싱 (원문 복구 불가)        | `models.py` set_password |
| **무차별 대입**   | Flask-Limiter (분당 5회 제한)      | `auth/routes.py` @limiter |
| **사용자 나열**  | "이메일 또는 비밀번호가 올바르지 않습니다" | `auth/routes.py` login   |
| **세션 탈취**    | session_protection="strong"      | `__init__.py`             |
| **CSRF**        | Flask-WTF CSRF 토큰 (1시간 유효)    | 모든 POST 폼               |
| **XSS**         | bleach로 허용된 HTML 태그만 필터링   | `board/routes.py`         |
| **SQL Injection**| SQLAlchemy ORM (파라미터 바인딩) | `models.py`, 모든 쿼리     |
| **IDOR**        | 작성자 ID 검증 (수정/삭제 시)       | `board/routes.py` edit/delete |
| **2FA**         | TOTP (Google Authenticator)      | `auth/routes.py` setup_2fa |
| **자동 스캐닝**  | 허니팟 경로 + 로그 기록             | `core/routes.py`, `auth/routes.py` |
| **보안 헤더**    | X-Frame-Options, X-Content-Type-Options 등 | `crackmeboard.nginx.conf` |

---

## 8. 서버 배포 구조

```
인터넷 사용자
    ↓
Nginx (포트 80)            ← 정적 파일 서빙 + 리버스 프록시 + 보안 헤더
    ↓ proxy_pass
Gunicorn (127.0.0.1:8000)  ← Flask 앱 실행 (워커 2개)
    ↓
Flask App                  ← 비즈니스 로직
    ↓
SQLite (instance/crackmeboard.db) ← 데이터 저장
```

### systemd (`crackmeboard.service`)
- 서버 재부팅 시 자동 실행
- 크래시 시 5초 후 자동 재시작 (`Restart=always`)
- 로그를 `/var/log/crackmeboard/`에 기록

### Nginx 보안 헤더
| 헤더                        | 역할                          |
|---------------------------|------------------------------|
| X-Frame-Options: DENY     | 클릭재킹 방지 (iframe embedding 차단)|
| X-Content-Type-Options    | MIME 스니핑 방지               |
| X-XSS-Protection          | 브라우저 내장 XSS 필터 활성화    |
| Referrer-Policy           | Referer 헤더 정보 제한          |

---

## 9. 발표용 핵심 포인트 (10분 발표 기준)

### 도입 (1분)
- "CrackMeBoard는 보안 동아리 웹 공방전을 위해 만든 회원제 게시판입니다"
- "상대팀이 공격할 수 있는 모든 웹 취약점에 대해 방어를 적용했습니다"

### 구조 설명 (2분)
- Flask + Blueprint 3개 (auth, board, core)
- SQLite DB (User, LoginLog, Post 3개 테이블)
- Nginx → Gunicorn → Flask 구조

### 보안 기능 설명 (5분) — 가장 중요
1. **비밀번호**: bcrypt 해싱 → DB 유출해도 원문 모름
2. **로그인**: Rate Limit + 실패 메시지 통일 → 무차별 대입/사용자 나열 방지
3. **2FA**: TOTP → 비밀번호 유출되어도 2단계 인증 필요
4. **XSS**: bleach로 HTML 태그 필터링
5. **SQLi**: ORM으로 자동 파라미터 바인딩
6. **IDOR**: 작성자 검증으로 남의 글 수정/삭제 차단
7. **CSRF**: 모든 POST에 CSRF 토큰
8. **허니팟**: 공격자 자동 스캔 탐지용 함정 경로

### 마무리 (2분)
- GitHub 링크 + 접속 링크 안내
- "상대팀이 공격할 수 있는 기본 웹 취약점 7가지에 대해 방어 적용"
