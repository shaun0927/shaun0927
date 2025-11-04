# 🚀 업그레이드 노트 (V2)

## 주요 개선사항

### 1. ✨ 정확도 대폭 향상
- **개선된 Vision AI 프롬프트**: 더 명확하고 구체적인 지침으로 대회 정보 추출 정확도 향상
- **상세한 검증 로직**: 추출된 데이터를 단계별로 검증
- **디버그 모드**: AI 응답을 실시간으로 확인 가능

### 2. 🤖 자동 통계 집계
**이제 Key Achievements가 자동으로 계산됩니다!**

```
🥇 Top 1% Finishes: X times   ← 자동 계산
🏅 Top 4% Finishes: X times   ← 자동 계산
🎖️ Top 10% Finishes: X times  ← 자동 계산
👥 Team Competitions: X times  ← 자동 계산
```

#### 집계 규칙:
- **해커톤 대회 제외**: `is_hackathon: true`인 대회는 통계에서 제외
- **Dacon + Kaggle 합산**: 두 플랫폼의 대회를 모두 포함
- **자동 백분율 계산**:
  - "20 / 802" → 2.49% → Top 4% 카운트
  - "1 / 709" → 1st Place → Top 1% 카운트
- **정확한 순위 인식**: "1st Place", "2nd Place", "Top X%" 모두 처리

### 3. 🏗️ 모듈화된 에이전트 시스템

**기존 (V1)**:
```
one_click_update.py → 모든 단계를 순차 실행
```

**개선 (V2)**:
```
Agent 1: Screenshot Capture    → 스크린샷 캡처
    ↓
Agent 2: Vision AI Analysis    → AI 분석 & JSON 생성
    ↓
Agent 3: Data Validation       → 데이터 검증
    ↓
Agent 4: README Generation     → README 업데이트
    ↓
Agent 5: Git Operations        → Git 커밋 & 푸시
```

#### 에이전트별 역할:

**Agent 1 (Screenshot Capture)**
- Selenium으로 Dacon/Kaggle 페이지 접근
- 전체 페이지 스크린샷 캡처
- 파일 생성 확인

**Agent 2 (Vision AI Analysis)**
- Claude Vision AI로 이미지 분석
- 대회 정보 추출 (ongoing/completed 구분)
- competitions.json 자동 생성
- 해커톤 및 코드 링크 보존

**Agent 3 (Data Validation)**
- JSON 구조 검증
- 필수 필드 확인
- 통계 정보 검증
- 요약 정보 출력

**Agent 4 (README Generation)**
- competitions.json 기반 README 생성
- 테이블 업데이트
- 타임스탬프 추가

**Agent 5 (Git Operations)**
- 변경사항 자동 커밋
- GitHub에 푸시
- 실패 시 경고 (강제 중단 없음)

### 4. 🔍 향상된 데이터 추출

#### Ongoing 대회 인식 개선
- 이전: 일부 ongoing 대회를 놓치는 문제
- 개선: 모든 진행 중인 대회를 정확히 식별

#### Completed 대회 정보 보완
- 이전: 기본 정보만 추출
- 개선: 순위, 카테고리, 링크 등 모든 정보 정확히 추출

#### 순위 텍스트 자동 계산
```python
# 예시
"20 / 802" → 계산 → 2.49% → "Top 3%"
"4 / 204" → 계산 → 1.96% → "Top 2%"
"1 / 709" → 인식 → "1st Place"
```

### 5. 🛡️ 데이터 보존 강화

#### 해커톤 대회 보존
- 프로필에 표시되지 않는 해커톤 대회 자동 유지
- 통계 집계에서는 제외

#### 코드 링크 보존
- AI가 추출하지 못한 기존 코드 링크 유지
- Dacon과 Kaggle 모두 적용

#### 기간순 자동 정렬
- 최신 대회가 상단에 표시되도록 자동 정렬

## 파일 구조 변경

### 새로운 파일
```
analyze_screenshots_v2.py    ← 개선된 Vision AI 분석
one_click_update_v2.py       ← 모듈화된 메인 스크립트
UPGRADE_NOTES.md            ← 이 문서
```

### 기존 파일 (호환성 유지)
```
analyze_screenshots.py       ← V1 (백업용)
one_click_update.py         ← V1 (백업용)
```

## 사용법 (변경 없음!)

**여전히 `UPDATE.bat`를 더블클릭하면 끝!**

내부적으로 V2 시스템이 자동으로 실행됩니다.

## V1 vs V2 비교

| 기능 | V1 | V2 |
|------|----|----|
| **AI 프롬프트** | 기본 | 개선 (상세 지침) |
| **통계 집계** | 수동 | 자동 (Dacon+Kaggle) |
| **에이전트 구조** | 단일 스크립트 | 5개 모듈화 에이전트 |
| **데이터 검증** | 없음 | 3단계 검증 |
| **디버그 모드** | 없음 | AI 응답 실시간 출력 |
| **오류 복구** | 전체 중단 | 단계별 처리 |
| **해커톤 보존** | 기본 | 강화 (코드 링크 포함) |
| **Ongoing 인식** | 부정확 | 정확 |

## 기술적 개선사항

### 1. 프롬프트 엔지니어링
```python
# V1: 간단한 프롬프트
"이 이미지에서 대회 정보를 추출해주세요"

# V2: 구조화된 프롬프트
"""
⚠️ 중요 지침:
1. 모든 대회를 빠짐없이 추출
2. ongoing과 completed 명확히 구분
3. 순위 정확히 읽기

📊 추출할 정보:
- rank: "X of Y"
- tier: "Competition Tier (Top Z%)"
- completed: [...]
- ongoing: [...]

🔍 순위 텍스트 규칙:
- 1위: "1st Place"
- ...
"""
```

### 2. 자동 통계 집계 알고리즘
```python
def calculate_achievements(dacon_completed, kaggle_completed):
    # 1. 해커톤 제외
    non_hackathon = [c for c in dacon if not c.get('is_hackathon')]

    # 2. Dacon + Kaggle 합산
    all_comps = non_hackathon + kaggle

    # 3. 백분율 자동 계산
    for comp in all_comps:
        if ranking_text == "1st Place":
            top1_count += 1
        elif percentage <= 1:
            top1_count += 1
        # ...

    return {"top1": ..., "top4": ..., "top10": ..., "teams": ...}
```

### 3. 모듈화 에이전트 패턴
```python
class UpdateAgent:
    def log(self, message): ...
    def run_command(self, cmd): ...

class ScreenshotAgent(UpdateAgent):
    def execute(self):
        # 스크린샷 캡처 로직
        return success

# Agent 순차 실행
for agent in agents:
    if not agent.execute():
        abort()
```

## 문제 해결

### V2 관련 이슈

**Q: V2가 실행되지 않아요**
A: `UPDATE.bat`가 `one_click_update_v2.py`를 호출하는지 확인하세요.

**Q: 통계가 자동으로 업데이트되지 않아요**
A: `analyze_screenshots_v2.py`가 실행되는지 확인하세요. 로그에 `[STATISTICS]` 메시지가 나타나야 합니다.

**Q: AI 응답을 보고 싶어요**
A: `analyze_screenshots_v2.py`를 직접 실행하면 `[DEBUG]` 섹션에서 AI 응답을 볼 수 있습니다.

**Q: V1으로 롤백하고 싶어요**
A: `UPDATE.bat`에서 `one_click_update_v2.py` → `one_click_update.py`로 변경하세요.

## 향후 계획

- [ ] 병렬 처리: Agent 1과 2를 동시 실행
- [ ] 웹 UI: 브라우저에서 실행 결과 확인
- [ ] 스케줄러: 매주 자동 실행
- [ ] 알림: 완료 시 데스크톱 알림

---

**업그레이드 완료! 🎉**

이제 더 정확하고 자동화된 시스템으로 GitHub 프로필을 관리할 수 있습니다.
