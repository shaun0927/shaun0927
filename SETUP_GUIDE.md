# 원클릭 자동 업데이트 시스템 설정 가이드

## 🚀 소개

이 시스템은 **단 한 번의 클릭**으로 GitHub 프로필을 자동으로 업데이트합니다:

1. Dacon/Kaggle 페이지 스크린샷 자동 캡처
2. **GPT-4o-mini**가 스크린샷을 분석하여 대회 정보 추출
3. competitions.json 자동 업데이트
4. README.md 자동 생성
5. Git 커밋 및 푸시 자동 실행

## 📋 사전 준비사항

### 1. Python 패키지 설치

```bash
pip install -r requirements.txt
```

필요한 패키지:
- `selenium`: 브라우저 자동화 및 스크린샷 캡처
- `openai`: OpenAI GPT-4o-mini API 사용
- `python-dotenv`: .env 파일에서 환경 변수 로드
- `pytz`: 시간대 처리 (KST)

### 2. Chrome 브라우저 설치

Selenium이 Chrome을 사용하므로 Chrome 브라우저가 설치되어 있어야 합니다.

### 3. OpenAI API 키 설정 (중요!)

**이미 .env 파일에 API 키가 저장되어 있습니다!**

#### .env 파일 확인

프로젝트 루트의 `.env` 파일에 API 키가 저장되어 있습니다:
```
OPENAI_API_KEY=sk-proj-...
```

**주의**: `.env` 파일은 절대 GitHub에 업로드되지 않습니다! (`.gitignore`에 포함됨)

#### API 키 변경이 필요한 경우

`.env` 파일을 텍스트 에디터로 열어서 수정:
```
OPENAI_API_KEY=새로운_키_값
```

#### 새 API 키 발급 방법

1. [OpenAI Platform](https://platform.openai.com/) 접속
2. 로그인 또는 회원가입
3. API Keys 섹션에서 새 키 생성
4. 생성된 키를 `.env` 파일에 저장

## 🎯 사용 방법

### 방법 1: 배치 파일 실행 (가장 쉬움!)

**`UPDATE.bat` 파일을 더블클릭**하면 모든 과정이 자동으로 실행됩니다!

```
파일 탐색기 → C:\Users\shaun\Desktop\이력서\shaun0927\
→ UPDATE.bat 더블클릭 → 완료!
```

### 방법 2: Python 스크립트 직접 실행

```bash
cd "C:\Users\shaun\Desktop\이력서\shaun0927"
python one_click_update_v2.py
```

### 방법 3: 개별 단계 실행 (디버깅용)

```bash
# 1단계: 스크린샷 캡처
python auto_update.py

# 2단계: AI 분석 (GPT-4o-mini)
python analyze_screenshots_v2.py

# 3단계: README 업데이트
python update_readme_simple.py

# 4단계: Git 커밋 및 푸시 (수동)
git add .
git commit -m "Update competitions"
git push
```

## 🔍 각 파일 설명

### 핵심 파일

- **`UPDATE.bat`**: 원클릭 실행 배치 파일 (Windows)
- **`one_click_update_v2.py`**: 전체 프로세스 자동화 마스터 스크립트
- **`auto_update.py`**: Selenium으로 Dacon/Kaggle 페이지 스크린샷 캡처
- **`analyze_screenshots_v2.py`**: GPT-4o-mini로 스크린샷 분석 및 데이터 추출
- **`update_readme_simple.py`**: competitions.json 기반 README 생성
- **`.env`**: OpenAI API 키 저장 (Git에 업로드 안 됨)

### 데이터 파일

- **`competitions.json`**: 대회 정보 중앙 데이터베이스
- **`README.md`**: GitHub 프로필 (자동 생성됨)
- **`screenshots/`**: 캡처된 스크린샷 저장 폴더

## ⚙️ 자동화 프로세스 상세

```
┌─────────────────────┐
│   UPDATE.bat 실행   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 1. 스크린샷 캡처    │ ← auto_update.py
│   - Dacon 프로필    │
│   - Kaggle 프로필   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. AI 이미지 분석   │ ← analyze_screenshots_v2.py
│   - GPT-4o-mini     │
│   - 대회 정보 추출  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. JSON 업데이트    │
│   - competitions.json│
│   - 해커톤 보존     │
│   - 통계 자동 계산  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. README 생성      │ ← update_readme_simple.py
│   - 테이블 업데이트 │
│   - 타임스탬프 추가 │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Git 커밋/푸시    │
│   - Auto commit     │
│   - Push to GitHub  │
└─────────────────────┘
```

## 🛠️ 문제 해결

### API 키 오류

```
[ERROR] OPENAI_API_KEY not found!
```

**해결책**: `.env` 파일을 확인하세요
```bash
# .env 파일 내용 확인
type .env
```

### Selenium 오류

```
selenium.common.exceptions.WebDriverException
```

**해결책**: Chrome 브라우저가 설치되어 있는지 확인

### Git 푸시 실패

```
[WARN] Git push failed!
```

**해결책**:
- GitHub 인증 확인 (Personal Access Token 설정 필요)
- `git push` 수동 실행으로 확인

### 스크린샷이 비어있음

**해결책**:
- 인터넷 연결 확인
- Dacon/Kaggle 로그인 상태 확인 (auto_update.py의 URL 수정 필요)

### OpenAI API 호출 실패

```
[ERROR] Failed to analyze screenshot
```

**해결책**:
- API 키가 유효한지 확인
- OpenAI 크레딧 잔액 확인
- 인터넷 연결 확인

## 📝 수동 업데이트

AI 분석 없이 수동으로 competitions.json만 수정하려면:

1. `competitions.json` 파일 편집
2. `python update_readme_simple.py` 실행
3. Git 커밋 및 푸시

## 🔐 보안 주의사항

1. **API 키를 절대 GitHub에 업로드하지 마세요!**
2. `.env` 파일은 `.gitignore`에 포함되어 있습니다
3. API 키가 노출되면 즉시 재발급하세요
4. **.env 파일은 이미 생성되어 API 키가 저장되어 있습니다**

## 💡 팁

1. **정기적 업데이트**: 대회 참여 후 `UPDATE.bat` 실행
2. **해커톤 보존**: 시스템이 자동으로 해커톤 대회를 보존합니다
3. **타임스탬프**: 매 업데이트마다 KST 시간이 자동 기록됩니다
4. **Git 히스토리**: 모든 변경사항이 자동으로 커밋됩니다
5. **디버그 모드**: `python analyze_screenshots_v2.py` 직접 실행 시 AI 응답 확인 가능

## 🎉 완료!

이제 로컬 컴퓨터에서 `UPDATE.bat`를 더블클릭하는 것만으로 GitHub 프로필이 자동으로 업데이트됩니다!

**실행 위치**: 파일 탐색기 → `C:\Users\shaun\Desktop\이력서\shaun0927\UPDATE.bat`

---

문제가 발생하면 각 단계를 개별적으로 실행하여 어디서 오류가 발생하는지 확인하세요.
