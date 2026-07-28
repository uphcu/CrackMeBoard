# CrackMeBoard (터보시게시판)

보안 동아리 웹 공방전용 회원제 게시판 서비스.

## 기술 스택

| 영역 | 기술 |
|------|------|
| Back-end | Python 3.14 + Flask |
| Database | SQLite (SQLAlchemy ORM) |
| Web Server | Nginx + Gunicorn (systemd) |
| Front-end | HTML/CSS, Bootstrap 5, Vanilla JS |
| 배포 | AWS EC2 t3.micro |

## 보안 기능

- **인증**: bcrypt 비밀번호 해싱, Flask-Login 세션 관리 (strong protection, 12h)
- **2FA**: TOTP 기반 2차 인증 (pyotp, QR코드)
- **CSRF**: Flask-WTF CSRF 토큰
- **XSS 방지**: bleach HTML sanitize + Jinja2 autoescape
- **SQLi 방지**: SQLAlchemy prepared statements
- **IDOR 방지**: 게시글 소유자 검증
- **Rate Limiting**: 로그인 5회/분 per IP+username
- **허니팟**: 가짜 관리자 경로 탐지 및 404 응답
- **보안 헤더**: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy

## 구조

```
crackmeboard/
├── app/
│   ├── __init__.py        # Flask factory + extensions
│   ├── models.py          # User, LoginLog, Post 모델
│   ├── auth/              # 로그인/회원가입/2FA
│   ├── board/             # 게시판 CRUD
│   ├── core/              # 메인 페이지 + 허니팟
│   ├── templates/         # Jinja2 템플릿
│   └── static/            # CSS/JS
├── crackmeboard.service   # systemd unit (Gunicorn)
└── crackmeboard.nginx.conf # Nginx 설정
```

## 실행 방법

```bash
# 가상환경
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 구동
gunicorn -w 2 -b 127.0.0.1:8000 app:create_app()

# Nginx (별도)
sudo cp crackmeboard.nginx.conf /etc/nginx/sites-available/crackmeboard
sudo ln -s /etc/nginx/sites-available/crackmeboard /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

## 환경 변수

```bash
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///instance/crackmeboard.db  # optional, SQLite default
TOTP_ISSUER=CrackMeBoard
```

## 라이선스

MIT