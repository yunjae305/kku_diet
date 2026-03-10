# 건국대학교 글로컬캠퍼스 생활관 식단 챗봇

건국대학교 글로컬캠퍼스 기숙사(해오름학사 / 모시래학사)의 식단 정보를 카카오톡 챗봇으로 제공하는 서비스입니다.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 서버 | Python 3.12 + Flask 3.1 |
| 크롤링 | Requests + BeautifulSoup4 |
| 데이터베이스 | SQLite (`users.db`) |
| 이미지 생성 | Pillow |
| 챗봇 플랫폼 | 카카오 챗봇 (구 i-kakao) |
| 배포 | Render |

---

## 프로젝트 구조

```
kku-diet-chatbot/
├── app.py              # Flask 서버 및 API 엔드포인트
├── crawler.py          # 기숙사 홈페이지 식단 크롤러 (10분 TTL 캐시)
├── user_store.py       # SQLite 기반 사용자 데이터 저장소
├── image_gen.py        # 주간 식단 이미지 생성 (Pillow)
├── fonts/
│   └── NanumGothic.ttf # 한글 폰트 (레포에 포함)
├── Procfile            # Render 배포용 (gunicorn)
├── build.sh            # Render 빌드 스크립트
├── requirements.txt
└── .gitignore
```

---

## 기능 설명

### 1. 오늘/내일 학식 조회 (`POST /api/diet`)

오늘 또는 내일 식단을 텍스트로 반환합니다.

- 발화에 `"내일"` 포함 여부로 자동 분기
- 주말인 경우 "주말에는 식단이 없습니다" 안내
- 기숙사 미등록 시 등록 버튼(빠른답변) 제공
- **해오름학사**: 점심·저녁 / **모시래학사**: 아침·점심·저녁

**응답 예시 (해오름학사):**
```
[해오름학사 03/10 식단]

🍴 점심:
계란볶음밥/쌀밥
아욱국
...

🌙 저녁:
쌀밥
부대찌개
...
```

---

### 2. 이번 주 학식 조회 (`POST /api/weekly`)

이번 주 월~금 전체 식단을 PNG 이미지로 반환합니다.

- 요청 즉시 전체 식단 크롤링 후 이미지 생성 (5분간 캐싱)
- 월~금 5일치 식단을 표 형식으로 표시
- 오늘 날짜 컬럼 강조 표시
- 한글 폰트(NanumGothic)는 레포에 포함되어 있어 자동 적용

---

### 3. 내 정보 조회 (`POST /api/myinfo`)

현재 등록된 기숙사 정보를 반환합니다.

---

### 4. 설정 (`POST /api/settings`)

현재 등록된 기숙사를 확인하고 변경할 수 있습니다.

---

### 5. 기숙사 등록

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /api/register/haeoreum` | 해오름학사 등록 |
| `POST /api/register/mosirae` | 모시래학사 등록 |

---

## 크롤링 방식

기숙사 홈페이지(`dorm.kku.ac.kr`)는 세션 없이 직접 접근 시 `landing.do`로 리다이렉트됩니다.
이를 해결하기 위해 아래 3단계 세션 흐름을 구현했습니다.

```
① GET /landing.do        → JSESSIONID 쿠키 획득
② GET /main.do?dormType= → 기숙사 컨텍스트 세션 설정
③ GET /weekly_diet.do    → 식단 HTML 파싱
```

파싱된 데이터는 **10분 TTL 메모리 캐시**에 저장되어 반복 요청 시 크롤링을 생략합니다.

---

## 데이터 저장

사용자별 기숙사 설정은 SQLite DB(`users.db`)에 저장됩니다.

```sql
CREATE TABLE users (
    user_id    TEXT PRIMARY KEY,   -- 카카오 사용자 ID
    dorm       TEXT NOT NULL,      -- 'haeoreum' | 'mosirae'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

> ⚠️ Render 재배포 시 `users.db`가 초기화되므로 사용자가 기숙사를 재등록해야 합니다.

---

## 배포 방식 (Render)

### 사전 준비

GitHub 저장소를 Render에 연결합니다.

### Render 설정

| 항목 | 값 |
|------|-----|
| Environment | Python 3 |
| Build Command | `bash build.sh` |
| Start Command | `gunicorn app:app` |

### 코드 수정 반영

```bash
git add .
git commit -m "변경 내용"
git push origin master
# → Render 자동 재배포
```

---

## 카카오 챗봇 스킬 URL 연결표

| 기능 | 스킬 URL |
|------|----------|
| 오늘/내일 학식 | `POST /api/diet` |
| 이번 주 학식 | `POST /api/weekly` |
| 내 정보 | `POST /api/myinfo` |
| 설정 | `POST /api/settings` |
| 해오름학사 등록 | `POST /api/register/haeoreum` |
| 모시래학사 등록 | `POST /api/register/mosirae` |
