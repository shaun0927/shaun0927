#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개선된 스크린샷 분석 스크립트 (Anthropic API 사용)
- 더 정확한 프롬프트
- 데이터 검증 레이어
- 자동 통계 집계
"""

import json
import base64
import os
import re
from anthropic import Anthropic

def encode_image(image_path):
    """이미지를 base64로 인코딩"""
    with open(image_path, 'rb') as f:
        return base64.standard_b64encode(f.read()).decode('utf-8')

def analyze_dacon_screenshot(client):
    """Dacon 스크린샷 분석 - 개선된 버전"""
    print("[INFO] Analyzing Dacon screenshot with improved prompts...")

    image_path = "screenshots/dacon_competitions.png"
    if not os.path.exists(image_path):
        print("[ERROR] Dacon screenshot not found!")
        return None

    image_data = encode_image(image_path)

    prompt = """이 Dacon 프로필 페이지 이미지를 매우 정확하게 분석해주세요.

⚠️ 중요 지침:
1. 이미지에서 보이는 모든 대회를 빠짐없이 추출하세요
2. "ongoing" 상태인 대회와 "completed" 대회를 명확히 구분하세요
3. 각 대회의 순위 정보를 정확히 읽어주세요
4. 링크는 실제로 보이지 않으면 "https://dacon.io/competitions/official/XXXXX/overview/description" 형식 사용

📊 추출할 정보:

**1. 전체 프로필 정보**
- rank: 전체 순위 (예: "27 of 144,839")
- tier: 티어 정보 (예: "Competition Challenger (Top 0.01%)")

**2. 완료된 대회 (Completed Competitions)**
각 완료된 대회마다:
{
  "period": "YYYY.MM ~ YYYY.MM",
  "name": "대회 전체 이름",
  "category": "카테고리 (예: 정형, 분류 / NLP, LLM / 비전, 분류 등)",
  "ranking": "순위 표시 (1위: 🥇 1 / 709, 2위: 🥈 2 / 771, 아니면: 20 / 802)",
  "ranking_text": "순위 설명 (1st Place / 2nd Place / Top X%)",
  "link": "대회 링크 (보이지 않으면 https://dacon.io/competitions/official/XXXXX/overview/description)",
  "code_link": "-",
  "is_hackathon": true/false (대회명에 "해커톤" 포함 시 true)
}

**3. 진행 중인 대회 (Ongoing/Active Competitions)**
현재 진행 중인 모든 대회:
{
  "period": "YYYY.MM ~ YYYY.MM",
  "name": "대회 전체 이름",
  "category": "카테고리",
  "ranking": "현재 순위 (예: 16 / 264)",
  "link": "대회 링크"
}

🔍 순위 텍스트 계산 규칙:
- 1위: "1st Place"
- 2위: "2nd Place"
- 3위: "3rd Place"
- 상위 1% 이내: "Top 1%"
- 상위 4% 이내: "Top 4%"
- 상위 10% 이내: "Top 10%"
- 그 외: "Top X%" (실제 백분율 계산)

⚡ 주의사항:
- 모든 대회를 빠짐없이 추출하세요
- ongoing과 completed를 정확히 구분하세요
- 순위는 정확한 숫자로 입력하세요
- 카테고리는 대회 설명에서 추출하세요

JSON 형식으로만 응답해주세요:
{
  "rank": "...",
  "tier": "...",
  "completed": [...],
  "ongoing": [...]
}
"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8192,  # 토큰 수 증가
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )

    response_text = message.content[0].text
    print(f"\n[DEBUG] Dacon AI Response:\n{response_text}\n")

    # JSON 파싱
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)

        # 검증
        print(f"[VALIDATION] Completed: {len(data.get('completed', []))} competitions")
        print(f"[VALIDATION] Ongoing: {len(data.get('ongoing', []))} competitions")

        return data
    except Exception as e:
        print(f"[ERROR] Failed to parse Dacon response: {e}")
        print(f"Response: {response_text}")
        return None

def analyze_kaggle_screenshot(client):
    """Kaggle 스크린샷 분석 - 개선된 버전"""
    print("[INFO] Analyzing Kaggle screenshot with improved prompts...")

    image_path = "screenshots/kaggle_competitions.png"
    if not os.path.exists(image_path):
        print("[ERROR] Kaggle screenshot not found!")
        return None

    image_data = encode_image(image_path)

    prompt = """이 Kaggle 프로필 페이지 이미지를 매우 정확하게 분석해주세요.

⚠️ 중요 지침:
1. "Active Competitions"와 "Completed Competitions" 섹션을 구분하세요
2. 각 대회의 순위를 정확히 읽어주세요
3. 모든 대회를 빠짐없이 추출하세요

📊 추출할 정보:

**1. 완료된 대회 (Completed Competitions)**
{
  "period": "YYYY.MM ~ YYYY.MM",
  "name": "대회 이름",
  "category": "카테고리 (예: NLP, Computer Vision, Time Series 등)",
  "ranking": "순위 (Top 10% 이내면 🥉 추가, 예: 🥉 157 / 2212 또는 318 / 1136)",
  "ranking_text": "Top 10% 이내일 경우만 표시 (예: Top 7%)",
  "link": "Kaggle 대회 링크",
  "code_link": "GitHub 링크 (보이지 않으면 -)"
}

**2. 진행 중인 대회 (Active Competitions)**
{
  "period": "YYYY.MM ~ YYYY.MM",
  "name": "대회 이름",
  "category": "카테고리",
  "ranking": "TBD",
  "link": "Kaggle 대회 링크"
}

🔍 순위 텍스트 규칙:
- 상위 7% 이내면 "Top 7%"처럼 정확한 백분율 표시
- Top 10% 초과면 ranking_text 생략

JSON 형식으로만 응답:
{
  "completed": [...],
  "ongoing": [...]
}
"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )

    response_text = message.content[0].text
    print(f"\n[DEBUG] Kaggle AI Response:\n{response_text}\n")

    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)

        # 검증
        print(f"[VALIDATION] Completed: {len(data.get('completed', []))} competitions")
        print(f"[VALIDATION] Ongoing: {len(data.get('ongoing', []))} competitions")

        return data
    except Exception as e:
        print(f"[ERROR] Failed to parse Kaggle response: {e}")
        print(f"Response: {response_text}")
        return None

def calculate_ranking_percentage(ranking_str):
    """순위 문자열에서 백분율 계산 (예: "20 / 802" -> 2.49%)"""
    try:
        # "🥇 1 / 709" 또는 "20 / 802" 형식에서 숫자 추출
        match = re.search(r'(\d+)\s*/\s*(\d+)', ranking_str)
        if match:
            rank = int(match.group(1))
            total = int(match.group(2))
            percentage = (rank / total) * 100
            return percentage
    except:
        pass
    return None

def calculate_achievements(dacon_completed, kaggle_completed):
    """
    자동 통계 집계 - 해커톤 제외, Dacon + Kaggle 합산

    Returns:
        dict: {
            "top1": Top 1% 횟수,
            "top4": Top 4% 횟수,
            "top10": Top 10% 횟수,
            "teams": 총 참여 대회 수 (해커톤 제외)
        }
    """
    print("\n[INFO] Calculating achievements statistics...")

    top1_count = 0
    top4_count = 0
    top10_count = 0

    # Dacon 완료 대회 분석 (해커톤 제외)
    for comp in dacon_completed:
        if comp.get('is_hackathon', False):
            print(f"  [SKIP] Hackathon: {comp['name']}")
            continue

        ranking_text = comp.get('ranking_text', '')
        ranking_str = comp.get('ranking', '')

        print(f"  [DACON] {comp['name']}: {ranking_str} ({ranking_text})")

        # 1위/2위는 무조건 Top 1%
        if '1st Place' in ranking_text or '2nd Place' in ranking_text:
            top1_count += 1
            top4_count += 1
            top10_count += 1
            continue

        # "Top X%" 형식 처리
        if 'Top' in ranking_text:
            match = re.search(r'Top\s*(\d+)%', ranking_text)
            if match:
                percentage = int(match.group(1))
                if percentage <= 1:
                    top1_count += 1
                if percentage <= 4:
                    top4_count += 1
                if percentage <= 10:
                    top10_count += 1
                continue

        # 백분율 직접 계산
        percentage = calculate_ranking_percentage(ranking_str)
        if percentage is not None:
            print(f"    -> Calculated: {percentage:.2f}%")
            if percentage <= 1:
                top1_count += 1
            if percentage <= 4:
                top4_count += 1
            if percentage <= 10:
                top10_count += 1

    # Kaggle 완료 대회 분석
    for comp in kaggle_completed:
        ranking_text = comp.get('ranking_text', '')
        ranking_str = comp.get('ranking', '')

        print(f"  [KAGGLE] {comp['name']}: {ranking_str} ({ranking_text})")

        # "Top X%" 형식 처리
        if 'Top' in ranking_text:
            match = re.search(r'Top\s*(\d+)%', ranking_text)
            if match:
                percentage = int(match.group(1))
                if percentage <= 1:
                    top1_count += 1
                if percentage <= 4:
                    top4_count += 1
                if percentage <= 10:
                    top10_count += 1
                continue

        # 백분율 직접 계산
        percentage = calculate_ranking_percentage(ranking_str)
        if percentage is not None:
            print(f"    -> Calculated: {percentage:.2f}%")
            if percentage <= 1:
                top1_count += 1
            if percentage <= 4:
                top4_count += 1
            if percentage <= 10:
                top10_count += 1

    # 총 대회 수 (해커톤 제외)
    total_teams = len([c for c in dacon_completed if not c.get('is_hackathon', False)]) + len(kaggle_completed)

    result = {
        "top1": top1_count,
        "top4": top4_count,
        "top10": top10_count,
        "teams": total_teams
    }

    print(f"\n[STATISTICS] Top 1%: {top1_count}, Top 4%: {top4_count}, Top 10%: {top10_count}, Total: {total_teams}")

    return result

def preserve_hackathons(current_data, new_data):
    """기존 해커톤 대회와 코드 링크 보존"""
    if not current_data or 'dacon' not in current_data:
        return new_data

    print("\n[INFO] Preserving existing hackathons and code links...")

    # 기존 해커톤 대회 찾기
    hackathons = [comp for comp in current_data['dacon'].get('completed', [])
                  if comp.get('is_hackathon', False)]

    print(f"[INFO] Found {len(hackathons)} hackathon(s) to preserve")

    # 새 데이터의 completed에 해커톤이 없으면 추가
    for hackathon in hackathons:
        if not any(comp['name'] == hackathon['name']
                  for comp in new_data['dacon']['completed']):
            print(f"  [ADD] {hackathon['name']}")
            new_data['dacon']['completed'].append(hackathon)

    # 기존 대회의 code_link 보존 (AI가 추출 못하는 경우)
    for old_comp in current_data['dacon'].get('completed', []):
        if old_comp.get('code_link') and old_comp['code_link'] != '-':
            # 같은 이름의 대회 찾기
            for new_comp in new_data['dacon']['completed']:
                if new_comp['name'] == old_comp['name']:
                    if new_comp.get('code_link', '-') == '-':
                        print(f"  [PRESERVE] Code link for: {old_comp['name']}")
                        new_comp['code_link'] = old_comp['code_link']

    # Kaggle code_link도 보존
    if 'kaggle' in current_data and isinstance(current_data['kaggle'], dict):
        for old_comp in current_data['kaggle'].get('completed', []):
            if old_comp.get('code_link') and old_comp['code_link'] != '-':
                for new_comp in new_data['kaggle']['completed']:
                    if new_comp['name'] == old_comp['name']:
                        if new_comp.get('code_link', '-') == '-':
                            print(f"  [PRESERVE] Code link for: {old_comp['name']}")
                            new_comp['code_link'] = old_comp['code_link']

    # 기간순 정렬 (최신순)
    new_data['dacon']['completed'].sort(
        key=lambda x: x['period'],
        reverse=True
    )

    return new_data

def update_competitions_json(dacon_data, kaggle_data):
    """competitions.json 업데이트"""
    print("\n[INFO] Updating competitions.json...")

    # 기존 데이터 로드 (해커톤 보존용)
    current_data = None
    if os.path.exists('competitions.json'):
        with open('competitions.json', 'r', encoding='utf-8') as f:
            current_data = json.load(f)

    # 새 데이터 구성
    new_data = {
        "dacon": {
            "rank": dacon_data.get("rank", "27 of 144,839"),
            "tier": dacon_data.get("tier", "Competition Challenger (Top 0.01%)"),
            "achievements": {},
            "completed": dacon_data.get("completed", []),
            "ongoing": dacon_data.get("ongoing", [])
        },
        "kaggle": kaggle_data
    }

    # 해커톤 및 코드 링크 보존
    new_data = preserve_hackathons(current_data, new_data)

    # 업적 통계 자동 계산 (해커톤 제외)
    new_data["dacon"]["achievements"] = calculate_achievements(
        new_data["dacon"]["completed"],
        new_data["kaggle"]["completed"]
    )

    # 저장
    with open('competitions.json', 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print("[OK] competitions.json updated successfully!")

    # 요약 출력
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Dacon Rank: {new_data['dacon']['rank']}")
    print(f"Dacon Tier: {new_data['dacon']['tier']}")
    print(f"Dacon Completed: {len(new_data['dacon']['completed'])} competitions")
    print(f"Dacon Ongoing: {len(new_data['dacon']['ongoing'])} competitions")
    print(f"Kaggle Completed: {len(new_data['kaggle']['completed'])} competitions")
    print(f"Kaggle Ongoing: {len(new_data['kaggle']['ongoing'])} competitions")
    print(f"Achievements: {new_data['dacon']['achievements']}")
    print("=" * 60)

    return new_data

def main():
    print("=" * 60)
    print("IMPROVED Screenshot Analysis System")
    print("=" * 60)

    # API 키 확인
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY environment variable not set!")
        print("[TIP] Set it with: set ANTHROPIC_API_KEY=your_key_here")
        return

    # Anthropic 클라이언트 초기화
    client = Anthropic(api_key=api_key)

    # Dacon 스크린샷 분석
    dacon_data = analyze_dacon_screenshot(client)
    if not dacon_data:
        print("[ERROR] Failed to analyze Dacon screenshot!")
        return

    print("[OK] Dacon analysis complete!")

    # Kaggle 스크린샷 분석
    kaggle_data = analyze_kaggle_screenshot(client)
    if not kaggle_data:
        print("[ERROR] Failed to analyze Kaggle screenshot!")
        return

    print("[OK] Kaggle analysis complete!")

    # competitions.json 업데이트
    update_competitions_json(dacon_data, kaggle_data)

    print("\n" + "=" * 60)
    print("[OK] All screenshots analyzed and processed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
