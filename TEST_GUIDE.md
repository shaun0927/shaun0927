# 🧪 테스트 가이드

## V2 시스템 테스트 방법

### 준비사항

1. **API 키 설정 확인**
```cmd
echo %ANTHROPIC_API_KEY%
```
- 출력이 없으면: `set ANTHROPIC_API_KEY=your_key_here` 실행

2. **패키지 설치 확인**
```bash
pip list | findstr anthropic
```
- 없으면: `pip install anthropic`

### 테스트 시나리오

#### 시나리오 1: 전체 워크플로우 테스트 (권장)

```bash
# UPDATE.bat 더블클릭 또는
python one_click_update_v2.py
```

**기대 결과**:
```
============================================================
IMPROVED ONE-CLICK AUTO UPDATE SYSTEM
Modular Agent Architecture
============================================================
Started at: 2025-XX-XX XX:XX:XX KST
============================================================

============================================================
STEP 1/5: Screenshot Capture
============================================================
[AGENT: Screenshot Capture] Starting screenshot capture...
[OK] Screenshots captured successfully!

============================================================
STEP 2/5: Vision AI Analysis
============================================================
[AGENT: Vision AI Analysis] Starting Vision AI analysis...
[DEBUG] Dacon AI Response:
{
  "rank": "27 of 144,839",
  ...
}
[VALIDATION] Completed: X competitions
[VALIDATION] Ongoing: 1 competition  ← "운수종사자..." 대회
[OK] Analysis completed and JSON updated!

============================================================
STEP 3/5: Data Validation
============================================================
[AGENT: Data Validation] Validating extracted data...
[INFO] Dacon Completed: X competitions
[INFO] Dacon Ongoing: 1 competitions  ← 확인!
[INFO] Achievements: {'top1': X, 'top4': X, 'top10': X, 'teams': X}
[OK] Data validation passed!

============================================================
STEP 4/5: README Generation
============================================================
[OK] README generated successfully!

============================================================
STEP 5/5: Git Operations
============================================================
[OK] Changes pushed to GitHub!

============================================================
[OK] ONE-CLICK UPDATE COMPLETED!
============================================================
```

#### 시나리오 2: 단계별 테스트

**1단계: 스크린샷만 캡처**
```bash
python auto_update.py
```
→ `screenshots/` 폴더 확인

**2단계: Vision AI 분석 (V2)**
```bash
python analyze_screenshots_v2.py
```

**확인 포인트**:
- `[DEBUG]` 섹션에서 AI 응답 확인
- `[VALIDATION]` 섹션에서 대회 수 확인
- **Ongoing: 1 competition** 확인 (운수종사자 대회)
- `[STATISTICS]` 섹션에서 자동 집계 확인

**3단계: competitions.json 확인**
```bash
type competitions.json
```

**확인할 내용**:
```json
{
  "dacon": {
    "rank": "27 of 144,839",
    "tier": "Competition Challenger (Top 0.01%)",
    "achievements": {
      "top1": X,  ← 자동 계산됨
      "top4": X,  ← 자동 계산됨
      "top10": X, ← 자동 계산됨
      "teams": X  ← Dacon + Kaggle 합산 (해커톤 제외)
    },
    "completed": [...],
    "ongoing": [
      {
        "period": "2025.XX ~ 2025.XX",
        "name": "운수종사자 인지적 특성 데이터를 활용한 교통사고 위험 예측 AI 경진대회",
        "category": "정형 | 회귀",
        "ranking": "X / Y",
        "link": "..."
      }
    ]
  },
  "kaggle": {...}
}
```

**4단계: README 확인**
```bash
python update_readme_simple.py
type README.md | findstr "Key Achievements"
```

**확인할 내용**:
```markdown
### 🏆 Key Achievements
🥇 **Top 1% Finishes: X times**  ← 자동 계산됨
🏅 **Top 4% Finishes: X times**  ← 자동 계산됨
🎖️ **Top 10% Finishes: X times** ← 자동 계산됨
👥 **Team Competitions: X times** ← Dacon + Kaggle (해커톤 제외)
```

#### 시나리오 3: 통계 집계 검증

**수동 검증**:
1. `competitions.json` 열기
2. Dacon `completed`에서 `is_hackathon: false`인 대회만 선택
3. Kaggle `completed` 대회 추가
4. 각 대회의 `ranking_text` 확인:
   - "1st Place" or "2nd Place" → Top 1% 카운트
   - "Top X%" (X ≤ 1) → Top 1% 카운트
   - "Top X%" (X ≤ 4) → Top 4% 카운트
   - "Top X%" (X ≤ 10) → Top 10% 카운트

**자동 검증 (Python)**:
```python
import json

with open('competitions.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Dacon (해커톤 제외)
dacon_non_hackathon = [c for c in data['dacon']['completed']
                       if not c.get('is_hackathon', False)]

# Kaggle
kaggle_all = data['kaggle']['completed']

# 총 대회 수
total = len(dacon_non_hackathon) + len(kaggle_all)

print(f"Dacon (비해커톤): {len(dacon_non_hackathon)}")
print(f"Kaggle: {len(kaggle_all)}")
print(f"Total: {total}")
print(f"Calculated: {data['dacon']['achievements']['teams']}")
print(f"Match: {total == data['dacon']['achievements']['teams']}")
```

### 문제 해결

#### 문제 1: Ongoing이 여전히 잘못 추출됨

**증상**:
```json
"ongoing": [
  {
    "name": "중소상인 AI 전환지원",  ← 이미 완료된 대회
    ...
  }
]
```

**해결**:
1. Dacon 프로필 페이지에서 실제로 ongoing인지 확인
2. 스크린샷 `screenshots/dacon_competitions.png` 확인
3. AI에게 더 명확한 지침 필요 시 프롬프트 수정

#### 문제 2: 통계가 맞지 않음

**증상**:
```json
"achievements": {
  "top1": 0,  ← 실제로는 2개인데
  ...
}
```

**디버그**:
```bash
python analyze_screenshots_v2.py
```
→ `[STATISTICS]` 섹션 확인

**확인할 점**:
- `ranking_text` 필드가 제대로 설정되었는지
- 백분율 계산이 정확한지
- 해커톤 대회가 제외되었는지

#### 문제 3: API 키 오류

**증상**:
```
[ERROR] ANTHROPIC_API_KEY environment variable not set!
```

**해결**:
```cmd
set ANTHROPIC_API_KEY=your_key_here
```

### 성공 체크리스트

- [ ] `UPDATE.bat` 실행 완료
- [ ] Ongoing에 "운수종사자..." 대회만 표시됨
- [ ] Completed에 모든 완료 대회가 정확히 표시됨
- [ ] `achievements` 통계가 자동으로 계산됨
- [ ] README의 Key Achievements가 업데이트됨
- [ ] Git 커밋 및 푸시 성공
- [ ] GitHub 프로필에 변경사항 반영됨

### 최종 검증

**GitHub에서 확인**:
1. https://github.com/shaun0927/shaun0927 접속
2. Key Achievements 숫자 확인
3. 완료된 대회 테이블 확인
4. 진행 중인 대회 테이블 확인 (운수종사자 대회만 있어야 함)
5. Last updated 시간 확인

---

**테스트 완료 후**:
- ✅ 모두 정상 → 문제 없음!
- ❌ 문제 발견 → `TEST_GUIDE.md`의 문제 해결 섹션 참조
- ❓ 여전히 문제 → 로그 전체를 복사하여 이슈 보고
