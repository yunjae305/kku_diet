# 건국대학교 글로컬캠퍼스 생활관 식단 챗봇

건국대학교 글로컬캠퍼스 기숙사(해오름학사 / 모시래학사)의 식단 정보를 카카오톡 챗봇으로 제공하는 서비스입니다.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 서버 | Python 3.12 + Flask 3.1 |
| 크롤링 | Requests + BeautifulSoup4 |
| 데이터베이스 | Google Cloud Firestore |
| 이미지 생성 | Pillow |
| 챗봇 플랫폼 | 카카오 챗봇 (구 i-kakao) |
| 배포 | Google Cloud Functions (서버리스) |

---

## 프로젝트 구조

```
kku-diet-chatbot/
├── app.py           # Flask 서버 및 API 엔드포인트 + Cloud Functions 핸들러
├── crawler.py       # 기숙사 홈페이지 식단 크롤러 (10분 TTL 캐시)
├── user_store.py    # Firestore 기반 사용자 데이터 저장소
├── image_gen.py     # 주간 식단 이미지 생성 (Pillow)
├── requirements.txt
├── .gcloudignore    # Cloud Functions 배포 제외 파일 목록
└── .gitignore
```

---

## 기능 설명

### 1. 오늘 학식 조회 (`POST /api/diet`)
오늘 날짜의 식단을 텍스트로 반환합니다.

- utterance(발화)에 `"내일"` 포함 여부로 오늘/내일 자동 분기
- 주말인 경우 "주말에는 식단이 없습니다" 안내
- 기숙사 미등록 시 등록 버튼(빠른답변) 제공
- **해오름학사**: 점심·저녁 / **모시래학사**: 아침·점심·저녁

**응답 예시 (해오름학사):**
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

**응답 예시 (모시래학사):**
```
[모시래학사 03/10 식단]

🌅 아침:
쌀밥
미역국
...

🍴 점심:
쌀밥
된장찌개
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
이번 주 월~금 전체 식단을 텍스트 한 장으로 반환합니다.

- 월~금 5일치 식단을 한눈에 표시
- 기숙사별 식사 종류에 맞게 출력 (해오름: 점심·저녁 / 모시래: 아침·점심·저녁)
- 식단이 없는 날(공휴일 등)은 "식단 정보 없음" 표시

**응답 예시:**
```
[해오름학사 이번주 식단]

📅 월 (03/10)
🍴 쌀밥, 된장국, ...
🌙 쌀밥, 부대찌개, ...

📅 화 (03/11)
🍴 계란볶음밥, ...
🌙 쌀밥, 김치찌개, ...
...
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

## 배포 방식 (Google Cloud Functions)

서버리스 방식으로 배포합니다. 사용자가 챗봇에 말을 걸 때만 실행되므로 비용이 거의 없고, Render 무료 플랜처럼 휴면 상태(30초 대기)가 없습니다.

### 사전 준비

1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. **Cloud Functions API** 활성화
3. **Cloud Firestore API** 활성화 → Firestore 데이터베이스 생성 (Native 모드)
4. [Google Cloud SDK](https://cloud.google.com/sdk) 설치 후 로그인

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 배포 명령

```bash
gcloud functions deploy kku-diet \
  --gen2 \
  --runtime=python312 \
  --region=asia-northeast3 \
  --source=. \
  --entry-point=kku_diet \
  --trigger-http \
  --allow-unauthenticated \
  --memory=512MB \
  --timeout=60s
```

### 코드 수정 반영 절차

```bash
# 1. 로컬에서 코드 수정
git add .
git commit -m "변경 내용"
git push origin master

# 2. 재배포
gcloud functions deploy kku-diet \
  --gen2 --runtime=python312 --region=asia-northeast3 \
  --source=. --entry-point=kku_diet \
  --trigger-http --allow-unauthenticated
```

### 배포 후 카카오 스킬 URL 형식

```
https://asia-northeast3-YOUR_PROJECT_ID.cloudfunctions.net/kku-diet/api/diet
https://asia-northeast3-YOUR_PROJECT_ID.cloudfunctions.net/kku-diet/api/weekly
...
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
