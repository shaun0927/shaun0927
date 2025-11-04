# 🔄 README 자동 업데이트 가이드

## 📖 개요

이 스크립트는 `competitions.json` 파일의 대회 정보를 읽어서 README.md를 자동으로 업데이트합니다.

**주요 기능:**
- ✅ Dacon 순위 및 통계 업데이트
- ✅ 완료된 대회/진행중인 대회 테이블 생성
- ✅ Kaggle 대회 정보 업데이트
- ✅ 해커톤 대회 자동 보존
- ✅ 업데이트 시간 자동 기록 (KST 기준)

---

## 🚀 빠른 시작

### 1. 패키지 설치 (최초 1회)

```bash
pip install pytz
```

### 2. 대회 정보 업데이트

`competitions.json` 파일을 열어서 최신 대회 정보로 수정합니다.

### 3. 스크립트 실행

```bash
python update_readme_simple.py
```

### 4. Git 커밋 & 푸시

```bash
git add README.md competitions.json
git commit -m "Update competition results"
git push origin main
```

---

## 📝 competitions.json 편집 가이드

### 기본 구조

```json
{
  "dacon": {
    "rank": "27 of 144,839",
    "tier": "Competition Challenger (Top 0.01%)",
    "achievements": {
      "top1": 2,
      "top4": 5,
      "top10": 9,
      "teams": 14
    },
    "completed": [ /* 완료된 대회 목록 */ ],
    "ongoing": [ /* 진행중인 대회 목록 */ ]
  },
  "kaggle": [ /* Kaggle 대회 목록 */ ]
}
```

### 새 대회 추가하기

#### 완료된 대회

`completed` 배열의 **최상단**에 새 대회를 추가합니다:

```json
{
  "period": "2025.10 ~ 2025.11",
  "name": "토스 NEXT ML CHALLENGE : CTR 모델 개발",
  "category": "추천시스템, 금융",
  "ranking": "🥇 1 / 709",
  "ranking_text": "1st Place",
  "link": "https://dacon.io/competitions/official/XXXXX/overview/description",
  "code_link": "-"
}
```

**필드 설명:**
- `period`: 대회 기간 (형식: YYYY.MM ~ YYYY.MM)
- `name`: 대회명
- `category`: 분야 (콤마로 구분)
- `ranking`: 순위 (이모지 포함 가능)
- `ranking_text`: 순위 텍스트 (Top X%, 1st Place 등) - 선택사항
- `link`: 대회 URL
- `code_link`: 코드 공유 링크 (없으면 `-`)
- `is_hackathon`: 해커톤 여부 (true/false) - 해커톤만 추가

#### 진행중인 대회

`ongoing` 배열에 추가:

```json
{
  "period": "2025.07 ~ 2025.08",
  "name": "2025 전력사용량 예측",
  "category": "시계열, 에너지",
  "ranking": "109 / 269",
  "link": "https://dacon.io/competitions/official/236531/overview/description"
}
```

#### Kaggle 대회

`kaggle` 배열에 추가:

```json
{
  "period": "2024.10 ~ 2025.04",
  "name": "AI Mathematical Olympiad - Progress Prize 2",
  "category": "NLP, Mathematical Reasoning",
  "ranking": "🥉 157 / 2212",
  "ranking_text": "Top 7%",
  "link": "https://www.kaggle.com/competitions/ai-mathematical-olympiad-progress-prize-2",
  "code_link": "https://github.com/shaun0927/AIMO-2-Solution"
}
```

### 대회 이동하기 (진행중 → 완료)

1. `ongoing` 배열에서 대회 객체를 복사
2. 최종 순위 정보 업데이트
3. `completed` 배열의 **최상단**에 붙여넣기
4. `ongoing` 배열에서 삭제

---

## 🎯 사용 예시

### 예시 1: 새 1위 대회 추가

```bash
# 1. competitions.json 열기
# 2. completed 배열 최상단에 추가:
{
  "period": "2025.11 ~ 2025.12",
  "name": "새로운 ML 대회",
  "category": "추천시스템",
  "ranking": "🥇 1 / 500",
  "ranking_text": "1st Place",
  "link": "https://dacon.io/...",
  "code_link": "-"
}

# 3. achievements 업데이트: "top1": 2 -> 3

# 4. 스크립트 실행
python update_readme_simple.py

# 5. 커밋
git add README.md competitions.json
git commit -m "Add new 1st place competition"
git push
```

### 예시 2: 진행중 대회 순위 업데이트

```bash
# 1. competitions.json의 ongoing 배열에서 대회 찾기
# 2. ranking 필드 업데이트
# 3. 스크립트 실행
python update_readme_simple.py
```

---

## ⚙️ 주의사항

### 해커톤 대회 보존

- 해커톤은 Dacon 프로필에 표시되지 않습니다
- **`is_hackathon: true` 플래그를 추가**하면 자동으로 보존됩니다
- 삭제하지 않도록 주의하세요!

예시:
```json
{
  "name": "갑상선암 진단 분류 해커톤",
  "is_hackathon": true,
  // ... 기타 필드
}
```

### 업데이트 순서

1. **완료된 대회**: 최신 대회가 **맨 위**에 표시됩니다
2. **진행중인 대회**: 순서 상관없음
3. **Kaggle**: 최신 대회가 **맨 위**에 표시됩니다

### JSON 형식 검증

JSON 형식이 잘못되면 스크립트가 오류를 발생시킵니다.
- https://jsonlint.com/ 에서 검증할 수 있습니다
- 콤마(,) 위치에 주의하세요
- 마지막 항목 뒤에는 콤마를 붙이지 않습니다

---

## 🔧 문제 해결

### "competitions.json 파일을 찾을 수 없습니다"

→ 리포지토리 루트 디렉토리에서 스크립트를 실행하세요

```bash
cd C:\Users\shaun\Desktop\이력서\shaun0927
python update_readme_simple.py
```

### "README.md 파일을 찾을 수 없습니다"

→ 리포지토리 루트 디렉토리에 README.md가 있는지 확인하세요

### JSON 파싱 오류

→ competitions.json의 형식을 확인하세요
- 중괄호 {}, 대괄호 [] 짝이 맞는지
- 콤마가 올바른 위치에 있는지
- 문자열이 큰따옴표 ""로 감싸져 있는지

---

## 📚 참고 자료

- [Dacon 프로필](https://dacon.io/myprofile/499579/home)
- [Kaggle 프로필](https://www.kaggle.com/najunghwan)
- [JSON 검증 사이트](https://jsonlint.com/)

---

## 💡 팁

1. **정기적으로 업데이트**: 대회 완료 직후 바로 업데이트하세요
2. **백업**: `competitions.json`을 수정하기 전에 백업하세요
3. **테스트**: 로컬에서 먼저 테스트 후 푸시하세요
4. **자동화**: GitHub Actions로 자동화도 가능합니다 (선택사항)
