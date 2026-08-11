# CrackMeBoard 발표 자료

---

## 도입 (1분)

안녕하세요. 저는 **CrackMeBoard**라는 회원제 게시판을 만들었습니다.

이 프로젝트는 보안 동아리 **웹 공방전**을 위해 만들어졌습니다.  
웹 공방전은 상대팀이 내 서버를 해킹해서 플래그를 얻고,  
나도 상대팀 서버를 해킹해서 플래그를 얻는 방식입니다.

그래서 "내 서버가 공격받았을 때 막을 수 있는가?"를 중심으로,  
웹에서 발생할 수 있는 대표적인 공격 9가지에 대해 방어를 적용했습니다.

---

## 기술 스택 (1분)

| 영역 | 사용 기술 |
|------|-----------|
| 백엔드 | Python 3.14, Flask 3.0 |
| 데이터베이스 | SQLite (SQLAlchemy ORM) |
| 웹 서버 | Nginx + Gunicorn (systemd) |
| 프론트엔드 | HTML/CSS, Bootstrap 5, Vanilla JS |
| 인증 | bcrypt 해싱, TOTP 2FA, CSRF 토큰 |

### 배포 구조

```
사용자 → Nginx (80) → Gunicorn (127.0.0.1:8000) → Flask App → SQLite DB
```

- Nginx: 리버스 프록시 + 보안 헤더 + 정적 파일 서빙
- Gunicorn: Flask 앱을 2개 워커로 실행, 크래시 시 자동 재시작
- systemd: 서버 재부팅 시 자동 실행

### 프로젝트 구조

```
app/
├── auth/     ← 회원가입, 로그인, 2FA, 허니팟
├── board/    ← 게시판 CRUD, 검색, 댓글
├── core/     ← 홈, 허니팟 catch-all
├── models.py ← DB 테이블 정의 (User, Post, Comment, LoginLog)
└── __init__.py ← 앱 초기화, 보안 설정
```

---

## 핵심: 보안 기능 (5분)

여기부터가 핵심입니다.  
각 공격 유형에 대해 **"공격이 뭔지 → 어떻게 막았는지"** 순서로 설명하겠습니다.

---

### 1. 무차별 대입 (Brute Force) → Rate Limit

**공격:** 비밀번호를 자동으로 계속 시도하는 공격.

**방어:** Flask-Limiter로 IP + 사용자명 기준 **분당 5회**만 로그인 시도 가능.

```python
@limiter.limit("5 per minute", key_func=_rate_limit_key)
def login():
    ...
```

- 5회 초과 시 429 Too Many Requests 응답
- 기본 제한: IP당 시간당 50회, 하루 200회

---

### 2. 비밀번호 유출 → bcrypt 해싱

**공격:** DB가 털렸을 때 비밀번호가 그대로 노출되는 문제.

**방어:** 비밀번호를 **해시**해서 저장. 원문 복구 불가.

```python
def set_password(self, password):
    self.password_hash = generate_password_hash(password)

def check_password(self, password):
    return check_password_hash(self.password_hash, password)
```

- `generate_password_hash`: 비밀번호를 일방향 암호화
- `check_password_hash`: 입력값을 해시해서 DB 해시와 비교
- DB가 유출되어도 원문 비밀번호를 알 수 없음

---

### 3. 사용자 나열 공격 → 에러 메시지 통일

**공격:** "존재하지 않는 이메일입니다" vs "비밀번호가 틀렸습니다"  
→ 메시지 차이로 어떤 이메일이 가입되어 있는지 추측 가능.

**방어:** 존재하지 않는 사용자든 비밀번호가 틀리든 **동일한 메시지** 반환.

```python
# 사용자 없음
if not user:
    return "이메일 또는 비밀번호가 올바르지 않습니다.", 401

# 비밀번호 틀림
if not user.check_password(password):
    return "이메일 또는 비밀번호가 올바르지 않습니다.", 401
```

→ 공격자가 이메일 존재 여부를 알 수 없음.

---

### 4. 세션 탈취 → 2FA (TOTP) + 세션 보호

**공격:** 세션 쿠키를 탈취해서 로그인 상태를 가로챔.

**방어 1: TOTP 2차 인증**

Google Authenticator 같은 앱이 30초마다 새로운 6자리 코드를 생성.

```
로그인 흐름:
1. 이메일 + 비밀번호 입력
2. 비밀번호 통과 → 2FA 활성화 여부 확인
3. 2FA 활성화 → 6자리 TOTP 코드 요청
4. TOTP 코드 검증 통과 → 세션 발급
```

→ 비밀번호가 유출되어도 2FA 코드 없으면 로그인 불가.

**방어 2: 세션 보호**

```python
login_manager.session_protection = "strong"
```

- 세션 IP/User-Agent가 변경되면 강제 로그아웃

---

### 5. XSS (크로스 사이트 스크립팅) → bleach

**공격:** 게시글에 `<script>...</script>`를 심어서,  
다른 사용자가 글을 읽을 때 악성 스크립트 실행.

**방어:** `bleach` 라이브러리로 허용된 HTML 태그만 필터링.

```python
ALLOWED_TAGS = ["b", "i", "u", "strong", "em", "p", "br",
                "ul", "ol", "li", "a", "pre", "code", "blockquote",
                "h1", "h2", "h3"]

def _sanitize_html(text):
    return bleach.clean(text, tags=ALLOWED_TAGS, strip=True)
```

- `<script>`, `<iframe>`, `onerror=` 등 위험 태그/속성 제거
- 게시글 제목, 내용, 댓글 모두에 적용

---

### 6. SQL Injection → ORM (파라미터 바인딩)

**공격:** 입력값에 SQL을 심어서 `' OR 1=1 --` 같은 구문으로 인증 우회.

**방어:** SQLAlchemy ORM 사용 → SQL을 직접 조립하지 않음.

```python
# ORM 사용 (자동 파라미터 바인딩)
user = User.query.filter_by(email=email).first()
post = Post.query.get_or_404(post_id)
```

→ 사용자 입력이 SQL에 직접 들어가지 않아 SQLi 불가.

---

### 7. IDOR (부적절한 객체 참조) → 작성자 검증

**공격:** URL에서 게시글 ID를 바꿔가며(`board/1/edit`, `board/2/edit`)  
남의 글을 수정하거나 삭제.

**방어:** 수정/삭제 시 작성자 ID와 현재 로그인한 사용자 ID 비교.

```python
@board_bp.route("/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def edit(post_id):
    post = Post.query.get_or_404(post_id)

    # IDOR protection: only author can edit
    if post.user_id != current_user.id:
        abort(403)
```

- 댓글 삭제에도 동일 적용: `comment.user_id != current_user.id` → 403

---

### 8. CSRF (크로스 사이트 요청 위조) → CSRF 토큰

**공격:** 사용자가 로그인한 상태에서, 악성 사이트가  
로그인 세션을 이용해 대신 요청을 보냄.

**방어:** 모든 POST 요청에 **CSRF 토큰** 필수.

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

```javascript
headers: {'X-CSRFToken': form.csrf_token.value}
```

- 토큰이 없거나 틀리면 400 Bad Request
- 토큰 유효시간 1시간 (`WTF_CSRF_TIME_LIMIT = 3600`)

---

### 9. 자동 스캐닝 → 허니팟 (Honeypot)

**공격:** 자동 스캐너가 `admin.php`, `.env`, `.git/config` 등  
흔한 관리자 경로/민감 파일을 무차별 스캔.

**방어:** 흔한 공격 경로를 **함정**으로 등록.

```python
HONEYPOT_PATHS = [
    "admin.php", "wp-admin", "wp-login.php", "phpmyadmin",
    ".env", ".git/config", "api/v1/admin", "actuator/health",
    "swagger-ui.html",
]

@core_bp.route("/<path:path>")
def catch_all(path):
    if any(hp in path.lower() for hp in HONEYPOT_PATHS):
        logging.warning(f"HONEYPOT TRIGGERED: /{path} from {request.remote_addr}")
        return abort(404)  # 그냥 404 반환
```

- 공격자 IP, 경로, 시간을 로그에 기록
- "이건 허니팟이다"라고 들키지 않게 그냥 404

---

## 보안 헤더 (Nginx)

| 헤더 | 역할 |
|------|------|
| X-Frame-Options: DENY | 클릭재킹 방지 (iframe 임베딩 차단) |
| X-Content-Type-Options: nosniff | MIME 스니핑 방지 |
| X-XSS-Protection | 브라우저 내장 XSS 필터 활성화 |
| Referrer-Policy | Referer 헤더 정보 제한 |

---

## 데모 (2분)

- 회원가입 → 로그인 → 2FA 설정
- 게시글 작성 → 댓글 작성
- 검색 기능
- (선택) 허니팟 로그 확인

---

## 마무리 (1분)

CrackMeBoard는 웹 공방전을 위해 만든 회원제 게시판입니다.

웹에서 발생하는 9가지 주요 공격에 대해 방어를 적용했습니다:
1. 무차별 대입 → Rate Limit
2. 비밀번호 유출 → bcrypt 해싱
3. 사용자 나열 → 에러 메시지 통일
4. 세션 탈취 → 2FA + 세션 보호
5. XSS → bleach 태그 필터링
6. SQL Injection → ORM
7. IDOR → 작성자 검증
8. CSRF → CSRF 토큰
9. 자동 스캐닝 → 허니팟

- **GitHub:** https://github.com/uphcu/CrackMeBoard
- **접속:** http://54.180.87.9

이상입니다. 감사합니다.
