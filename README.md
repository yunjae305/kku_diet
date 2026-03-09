# 건국대학교 글로컬캠퍼스 생활관 식단 챗봇

건국대학교 글로컬캠퍼스 기숙사(해오름학사 / 모시래학사)의 식단 정보를 카카오톡 챗봇으로 제공하는 서비스입니다.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 서버 | Python 3.12 + Flask 3.1 |
| 크롤링 | Requests + BeautifulSoup4 |
| 데이터베이스 | SQLite3 (Python 내장) |
| 챗봇 플랫폼 | 카카오 챗봇 (구 i-kakao) |
| 배포 | Render (Cloud PaaS) |
| WSGI 서버 | Gunicorn |

---

## 프로젝트 구조

```
kku-diet-chatbot/
├── app.py           # Flask 서버 및 API 엔드포인트
├── crawler.py       # 기숙사 홈페이지 식단 크롤러
├── user_store.py    # SQLite 기반 사용자 데이터 저장소
├── Procfile         # Render 배포용 실행 명령 정의
├── requirements.txt
└── .gitignore
```

---

## 기능 설명

### 1. 오늘 학식 조회 (`POST /api/diet`)
오늘 날짜의 점심·저녁 식단을 텍스트로 반환합니다.

- utterance(발화)에 `"내일"` 포함 여부로 오늘/내일 자동 분기
- 주말인 경우 "주말에는 식단이 없습니다" 안내
- 기숙사 미등록 시 등록 버튼(빠른답변) 제공

**응답 예시:**
```
[해오름학사 03/10 식단]

🍴 점심:
계란볶음밥/쌀밥
아욱국
짜장덮밥소스
...

🌙 저녁:
쌀밥
부대찌개
...
```

---

### 2. 내일 학식 조회 (`POST /api/diet`)
오늘 학식 조회와 동일한 엔드포인트를 사용하며, 발화에 `"내일"` 이 포함된 경우 내일 식단을 반환합니다.

---

### 3. 이번 주 학식 조회 (`POST /api/weekly`)
이번 주 월~금 전체 식단을 **캐러셀 카드** 형태로 반환합니다.

- 요일별 카드 5장(월~금)을 슬라이드 형태로 표시
- 각 카드에 해당 날짜의 점심·저녁 식단 표시
- 식단이 없는 날(공휴일 등)은 "식단 정보 없음" 표시
- 카카오톡 basicCard description 230자 제한 준수

**카드 형태:**
```
┌──────────────┐  ┌──────────────┐
│  월 (03/09)  │  │  화 (03/10)  │
│ 🍴 점심      │  │ 🍴 점심      │  ...
│ 쌀밥, 미역국 │  │ 계란볶음밥   │
│ 🌙 저녁      │  │ 🌙 저녁      │
│ 쌀밥, ...    │  │ 쌀밥, ...    │
└──────────────┘  └──────────────┘
```

---

### 4. 내 정보 조회 (`POST /api/myinfo`)
현재 등록된 기숙사 정보를 반환합니다.

**응답 예시:**
```
⚙️ 현재 설정
• 기숙사: 해오름학사
```

---

### 5. 설정 (`POST /api/settings`)
현재 등록된 기숙사를 확인하고 변경할 수 있습니다.

- 현재 설정 표시
- 빠른답변 버튼으로 기숙사 변경 가능 (해오름학사 / 모시래학사)

---

### 6. 기숙사 등록
사용자의 카카오 ID와 기숙사 선택을 SQLite DB에 저장합니다.

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

- 카카오 사용자 ID는 해시값으로 제공되어 개인정보 식별 불가
- `users.db`는 `.gitignore`에 포함되어 GitHub에 업로드되지 않음

---

## 배포 방식 (Render)

이 프로젝트는 [Render](https://render.com)를 통해 클라우드에 배포됩니다.
GitHub 저장소와 연동되어 `master` 브랜치에 푸시하면 자동으로 재배포됩니다.

### 배포 구조

```
GitHub (master 브랜치)
    │
    └─► Render (자동 배포)
            │
            └─► gunicorn app:app (Procfile 기준)
```

### 환경 변수

| 변수명 | 설명 |
|--------|------|
| `PORT` | Render가 자동 주입하는 포트 번호 (기본값 5000) |

### 코드 수정 반영 절차

```bash
# 1. 로컬에서 코드 수정 후
git add .
git commit -m "변경 내용"
git push origin master

# 2. Render가 자동으로 감지하여 재배포 (약 1~2분 소요)
```

### Procfile

```
web: gunicorn app:app
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
