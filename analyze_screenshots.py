#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스크린샷 분석 스크립트 (Anthropic API 사용)
"""

import json
import base64
import os
from anthropic import Anthropic

def encode_image(image_path):
    """이미지를 base64로 인코딩"""
    with open(image_path, 'rb') as f:
        return base64.standard_b64encode(f.read()).decode('utf-8')

def analyze_dacon_screenshot(client):
    """Dacon 스크린샷 분석"""
    print("[INFO] Analyzing Dacon screenshot...")

    image_path = "screenshots/dacon_competitions.png"
    if not os.path.exists(image_path):
        print("[ERROR] Dacon screenshot not found!")
        return None

    image_data = encode_image(image_path)

    prompt = """이 Dacon 프로필 페이지 이미지를 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. 전체 순위 정보 (예: "27 of 144,839")
2. 티어 정보 (예: "Competition Challenger (Top 0.01%)")
3. 완료된 대회 목록 (ongoing이 아닌 것들):
   - period: 대회 기간 (예: "2025.10 ~ 2025.11")
   - name: 대회 이름
   - category: 대회 카테고리 (정형/비전/NLP 등)
   - ranking: 순위 (1위면 "🥇 1 / 709", 아니면 "20 / 802" 형식)
   - ranking_text: 순위 설명 (1위면 "1st Place", Top X%면 "Top X%")
   - link: 대회 링크 (보이면 추출, 안 보이면 "https://dacon.io/competitions/official/XXXXX/overview/description")
   - code_link: "-" (기본값)
   - is_hackathon: 해커톤이면 true (대회명에 "해커톤" 포함 시)

4. 진행 중인 대회 목록:
   - period, name, category, ranking, link

JSON 형식으로만 응답해주세요. 다른 설명은 필요 없습니다.
"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
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
    # JSON 파싱
    try:
        # Claude가 ```json ... ``` 형식으로 감쌀 수 있으므로 처리
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        return json.loads(response_text)
    except Exception as e:
        print(f"[ERROR] Failed to parse Dacon response: {e}")
        print(f"Response: {response_text}")
        return None

def analyze_kaggle_screenshot(client):
    """Kaggle 스크린샷 분석"""
    print("[INFO] Analyzing Kaggle screenshot...")

    image_path = "screenshots/kaggle_competitions.png"
    if not os.path.exists(image_path):
        print("[ERROR] Kaggle screenshot not found!")
        return None

    image_data = encode_image(image_path)

    prompt = """이 Kaggle 프로필 페이지 이미지를 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. 완료된 대회 목록 (Completed Competitions):
   - period: 대회 기간 (예: "2024.10 ~ 2025.04")
   - name: 대회 이름
   - category: 대회 카테고리
   - ranking: 순위 (Top 10% 이내면 🥉 이모지 추가, 예: "🥉 157 / 2212" 또는 "318 / 1136")
   - ranking_text: Top X% 계산 (Top 10% 이내일 경우만, 예: "Top 7%")
   - link: Kaggle 대회 링크
   - code_link: GitHub 링크가 보이면 추출, 없으면 "-"

2. 진행 중인 대회 목록 (Active Competitions):
   - period, name, category, ranking: "TBD", link

JSON 형식으로만 응답해주세요. 다른 설명은 필요 없습니다.
"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
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
    # JSON 파싱
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        return json.loads(response_text)
    except Exception as e:
        print(f"[ERROR] Failed to parse Kaggle response: {e}")
        print(f"Response: {response_text}")
        return None

def preserve_hackathons(current_data, new_data):
    """기존 해커톤 대회 보존"""
    if not current_data or 'dacon' not in current_data:
        return new_data

    # 기존 해커톤 대회 찾기
    hackathons = [comp for comp in current_data['dacon'].get('completed', [])
                  if comp.get('is_hackathon', False)]

    # 새 데이터의 completed에 해커톤이 없으면 추가
    for hackathon in hackathons:
        # 같은 대회명이 없으면 추가
        if not any(comp['name'] == hackathon['name']
                  for comp in new_data['dacon']['completed']):
            new_data['dacon']['completed'].append(hackathon)

    # 기간순 정렬 (최신순)
    new_data['dacon']['completed'].sort(
        key=lambda x: x['period'],
        reverse=True
    )

    return new_data

def calculate_achievements(completed_competitions):
    """업적 통계 계산"""
    top1 = 0
    top4 = 0
    top10 = 0

    for comp in completed_competitions:
        ranking_text = comp.get('ranking_text', '')
        if '1st Place' in ranking_text or '2nd Place' in ranking_text:
            top1 += 1

        if 'Top' in ranking_text:
            # "Top X%" 형식에서 숫자 추출
            import re
            match = re.search(r'Top (\d+)%', ranking_text)
            if match:
                percentage = int(match.group(1))
                if percentage <= 1:
                    top1 += 1
                if percentage <= 4:
                    top4 += 1
                if percentage <= 10:
                    top10 += 1

    return {
        "top1": top1,
        "top4": top4,
        "top10": top10,
        "teams": len(completed_competitions)
    }

def update_competitions_json(dacon_data, kaggle_data):
    """competitions.json 업데이트"""
    print("[INFO] Updating competitions.json...")

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

    # 해커톤 보존
    new_data = preserve_hackathons(current_data, new_data)

    # 업적 통계 계산
    new_data["dacon"]["achievements"] = calculate_achievements(
        new_data["dacon"]["completed"]
    )

    # 저장
    with open('competitions.json', 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print("[OK] competitions.json updated successfully!")
    return new_data

def main():
    print("=" * 60)
    print("Screenshot Analysis with Anthropic API")
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

    print("=" * 60)
    print("[OK] All screenshots analyzed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
