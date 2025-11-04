#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간단한 README 업데이트 스크립트
competitions.json 파일의 대회 정보를 읽어서 README.md를 업데이트합니다.
"""

import json
import re
from datetime import datetime
import pytz


def load_competitions():
    """competitions.json 파일 로드"""
    try:
        with open('competitions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        create_sample_json()
        return None


def create_sample_json():
    """샘플 competitions.json 파일 생성"""
    print("[INFO] competitions.json 파일이 없습니다. 샘플 파일을 생성합니다.")
    sample = {
        "dacon": {
            "rank": "27 of 144,839",
            "tier": "Competition Challenger (Top 0.01%)",
            "achievements": {
                "top1": 2,
                "top4": 5,
                "top10": 9,
                "teams": 14
            },
            "completed": [
                {
                    "period": "2025.10 ~ 2025.11",
                    "name": "토스 NEXT ML CHALLENGE : CTR 모델 개발",
                    "category": "추천시스템, 금융",
                    "ranking": "🥇 1 / 709",
                    "ranking_text": "1st Place",
                    "link": "https://dacon.io/competitions/official/XXXXX/overview/description",
                    "code_link": "-",
                    "is_hackathon": False
                }
            ],
            "ongoing": []
        },
        "kaggle": [
            {
                "period": "2024.10 ~ 2025.04",
                "name": "AI Mathematical Olympiad - Progress Prize 2",
                "category": "NLP, Mathematical Reasoning",
                "ranking": "🥉 157 / 2212",
                "ranking_text": "Top 7%",
                "link": "https://www.kaggle.com/competitions/ai-mathematical-olympiad-progress-prize-2",
                "code_link": "https://github.com/shaun0927/AIMO-2-Solution"
            }
        ]
    }

    with open('competitions.json', 'w', encoding='utf-8') as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    print("[OK] competitions.json 샘플 파일이 생성되었습니다.")
    print("[TIP] 파일을 수정한 후 다시 실행해주세요.")


def generate_dacon_completed_table(competitions):
    """완료된 대회 테이블 HTML 생성"""
    rows = []

    for comp in competitions:
        # 코드 링크 처리
        if comp.get('code_link', '-') == '-':
            code_cell = '-'
        else:
            code_cell = f'<a href="{comp["code_link"]}">{"논문 정리" if "논문" in comp.get("code_link", "") else "코드 보기"}</a>'

        # 랭킹 표시 (1위는 강조)
        ranking = comp['ranking']
        if comp.get('ranking_text'):
            ranking = f"<b>{ranking}</b> ({comp['ranking_text']})"

        row = f'''    <tr>
      <td align="center">{comp['period']}</td>
      <td align="center"><a href="{comp['link']}">{comp['name']}</a></td>
      <td align="center">{comp['category']}</td>
      <td align="center">{ranking}</td>
      <td align="center">{code_cell}</td>
    </tr>'''
        rows.append(row)

    return '\n'.join(rows)


def generate_dacon_ongoing_table(competitions):
    """진행중인 대회 테이블 HTML 생성"""
    rows = []

    for comp in competitions:
        row = f'''    <tr>
      <td align="center">{comp['period']}</td>
      <td align="center"><a href="{comp['link']}">{comp['name']}</a></td>
      <td align="center">{comp['category']}</td>
      <td align="center">{comp.get('ranking', '-')}</td>
    </tr>'''
        rows.append(row)

    return '\n'.join(rows)


def generate_kaggle_table(competitions):
    """Kaggle 대회 테이블 HTML 생성"""
    rows = []

    for comp in competitions:
        # 코드 링크 처리
        if comp.get('code_link', '-') == '-':
            code_cell = '-'
        else:
            code_cell = f'<a href="{comp["code_link"]}">코드 보기</a>'

        # 랭킹 강조
        ranking = comp['ranking']
        if comp.get('ranking_text'):
            ranking = f"<b>{ranking}</b> ({comp['ranking_text']})"

        row = f'''    <tr>
      <td align="center">{comp['period']}</td>
      <td align="center"><a href="{comp['link']}">{comp['name']}</a></td>
      <td align="center">{comp['category']}</td>
      <td align="center">{ranking}</td>
      <td align="center">{code_cell}</td>
    </tr>'''
        rows.append(row)

    return '\n'.join(rows)


def update_readme(data):
    """README.md 업데이트"""
    print("[INFO] README.md를 업데이트하는 중...")

    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            readme = f.read()
    except FileNotFoundError:
        print("[ERROR] README.md 파일을 찾을 수 없습니다.")
        return

    # 1. Dacon 순위 업데이트
    dacon_data = data['dacon']
    readme = re.sub(
        r'<strong>Overall Rank: \d+ of [\d,]+</strong>',
        f'<strong>Overall Rank: {dacon_data["rank"]}</strong>',
        readme
    )
    readme = re.sub(
        r'Competition (?:Gold|Silver|Bronze|Challenger) \(Top [\d.]+%\)',
        dacon_data['tier'],
        readme
    )

    # 2. Key Achievements 업데이트
    achievements = dacon_data['achievements']
    readme = re.sub(
        r'🥇 <strong>Top 1% Finishes: \d+ times?</strong>',
        f'🥇 <strong>Top 1% Finishes: {achievements["top1"]} times</strong>',
        readme
    )
    readme = re.sub(
        r'🏅 <strong>Top 4% Finishes: \d+ times?</strong>',
        f'🏅 <strong>Top 4% Finishes: {achievements["top4"]} times</strong>',
        readme
    )
    readme = re.sub(
        r'🎖️ <strong>Top 10% Finishes: \d+ times?</strong>',
        f'🎖️ <strong>Top 10% Finishes: {achievements["top10"]} times</strong>',
        readme
    )

    # 3. 완료된 대회 테이블 업데이트
    completed_table = generate_dacon_completed_table(dacon_data['completed'])
    readme = re.sub(
        r'(<summary><strong>✅ 데이콘 완료된 대회.*?</thead>\s*<tbody>)(.*?)(</tbody>\s*</table>)',
        rf'\1\n{completed_table}\n    \3',
        readme,
        flags=re.DOTALL
    )

    # 4. 진행중인 대회 테이블 업데이트 (있는 경우)
    if dacon_data.get('ongoing'):
        ongoing_table = generate_dacon_ongoing_table(dacon_data['ongoing'])
        readme = re.sub(
            r'(<summary><strong>⏳ 데이콘 진행 중인 대회.*?</thead>\s*<tbody>)(.*?)(</tbody>\s*</table>)',
            rf'\1\n{ongoing_table}\n    \3',
            readme,
            flags=re.DOTALL
        )

    # 5. Kaggle 대회 테이블 업데이트
    if data.get('kaggle'):
        kaggle_table = generate_kaggle_table(data['kaggle'])
        readme = re.sub(
            r'(<summary><strong>🏆 캐글 대회.*?</thead>\s*<tbody>)(.*?)(</tbody>\s*</table>)',
            rf'\1\n{kaggle_table}\n    \3',
            readme,
            flags=re.DOTALL
        )

    # 6. 업데이트 시간 추가
    kst = pytz.timezone('Asia/Seoul')
    update_time = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S KST')

    # 업데이트 시간 표시 추가 (Data Science Competitions 섹션 상단)
    if '<!-- LAST_UPDATED -->' not in readme:
        readme = re.sub(
            r'(<h2 style="border-bottom: 2px solid #2391d9; display: inline-block; padding-bottom: 5px;">🏆 Data Science Competitions</h2>)',
            rf'\1\n  <!-- LAST_UPDATED -->\n  <p><em>Last updated: {update_time}</em></p>',
            readme
        )
    else:
        readme = re.sub(
            r'<!-- LAST_UPDATED -->.*?<p><em>Last updated:.*?</em></p>',
            f'<!-- LAST_UPDATED -->\n  <p><em>Last updated: {update_time}</em></p>',
            readme,
            flags=re.DOTALL
        )

    # 7. 파일 저장
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)

    print("[OK] README.md 업데이트 완료!")
    print(f"[INFO] Last updated: {update_time}")


def main():
    print("=" * 60)
    print("GitHub Profile README Updater")
    print("=" * 60)

    # competitions.json 로드
    data = load_competitions()
    if data is None:
        return

    # README 업데이트
    update_readme(data)

    print("=" * 60)
    print("[OK] 완료!")
    print("[TIP] 변경사항을 확인한 후 git commit & push 하세요.")
    print("=" * 60)


if __name__ == "__main__":
    main()
