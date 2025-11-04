# 🔄 GitHub Profile Competition Auto-Updater

이 스크립트는 Dacon과 Kaggle의 대회 정보를 자동으로 크롤링하여 README.md를 업데이트합니다.

## 📋 사전 준비

### 1. Python 설치
- Python 3.8 이상 필요

### 2. Chrome 브라우저 설치
- Selenium이 Chrome을 사용합니다

### 3. ChromeDriver 설치
**자동 설치 (권장):**
```bash
pip install webdriver-manager
```

**수동 설치:**
1. https://chromedriver.chromium.org/downloads 에서 Chrome 버전에 맞는 드라이버 다운로드
2. PATH에 추가하거나 프로젝트 폴더에 배치

### 4. 패키지 설치
```bash
pip install -r requirements.txt
```

## 🚀 사용 방법

### 방법 1: 자동 크롤링 (Selenium)
```bash
python update_competitions.py
```

**주의사항:**
- Dacon 프로필 페이지가 공개되어 있어야 합니다
- 크롤링에 10-20초 정도 소요됩니다
- 해커톤 대회는 자동으로 보존됩니다

### 방법 2: 수동 업데이트 (JSON 파일 사용)
```bash
# 1. competitions.json 파일 생성 및 편집
# 2. 스크립트 실행
python update_competitions.py --from-json
```

## 📝 competitions.json 형식

```json
{
  "dacon": {
    "completed": [
      {
        "name": "토스 NEXT ML CHALLENGE : CTR 모델 개발",
        "period": "2025.10 ~ 2025.11",
        "category": "추천시스템, 금융",
        "ranking": "🥇 1 / 709",
        "link": "https://dacon.io/competitions/official/XXXXX/overview/description",
        "is_hackathon": false
      }
    ],
    "ongoing": [
      {
        "name": "2025 전력사용량 예측",
        "period": "2025.07 ~ 2025.08",
        "category": "시계열, 에너지",
        "ranking": "109 / 269",
        "link": "https://dacon.io/competitions/official/236531/overview/description"
      }
    ]
  },
  "kaggle": [
    {
      "name": "AI Mathematical Olympiad - Progress Prize 2",
      "period": "2024.10 ~ 2025.04",
      "category": "NLP, Mathematical Reasoning",
      "ranking": "🥉 157 / 2212",
      "link": "https://www.kaggle.com/competitions/ai-mathematical-olympiad-progress-prize-2"
    }
  ]
}
```

## ⚙️ 기능

✅ **자동 크롤링**
- Dacon 완료/진행중 대회 자동 수집
- Kaggle 대회 정보 수집 (로그인 필요)

✅ **해커톤 보존**
- 기존 README의 해커톤 대회 자동 감지 및 보존
- 모든 해커톤은 "완료된 대회"로 표시

✅ **업데이트 시간 기록**
- 마지막 업데이트 시간 자동 표시 (KST 기준)

✅ **기존 형식 유지**
- README.md의 기존 레이아웃과 디자인 보존
- 대회 정보만 업데이트

## 🔧 트러블슈팅

### Chrome 브라우저를 찾을 수 없습니다
```bash
# webdriver-manager 사용 (권장)
pip install webdriver-manager
```

스크립트에서:
```python
from webdriver_manager.chrome import ChromeDriverManager
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
```

### Selenium이 페이지를 로드하지 못합니다
- 인터넷 연결 확인
- Dacon/Kaggle 사이트 접속 가능 여부 확인
- 수동으로 JSON 파일 사용 권장

### 해커톤이 삭제되었습니다
- 해커톤 키워드: "해커톤", "hackathon", "Hackathon"
- 대회명에 위 키워드가 없으면 일반 대회로 인식됩니다
- `update_competitions.py`의 `hackathon_keywords` 리스트에 키워드 추가 가능

## 📞 문의

문제가 발생하면 Issue를 생성해주세요.
