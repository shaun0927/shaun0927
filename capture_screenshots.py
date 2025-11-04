#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
완전 자동화된 대회 정보 업데이트 시스템
1. 스크린샷 캡처 (Selenium)
2. 이미지 분석 (이 스크립트가 캡처, 사용자가 Claude에게 전달)
3. competitions.json 업데이트
4. README 업데이트
"""

import json
import time
import os
import subprocess
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pytz


def setup_driver():
    """Selenium WebDriver 설정"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,3000")  # 긴 페이지 캡처
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    return webdriver.Chrome(options=chrome_options)


def capture_screenshots():
    """Dacon과 Kaggle 스크린샷 캡처"""
    print("=" * 60)
    print("Step 1: 스크린샷 캡처")
    print("=" * 60)

    os.makedirs("screenshots", exist_ok=True)

    dacon_url = "https://dacon.io/myprofile/499579/competition"
    kaggle_url = "https://www.kaggle.com/najunghwan/competitions"

    driver = setup_driver()

    try:
        # Dacon 캡처
        print("\n[1/2] Dacon 페이지 접속 중...")
        driver.get(dacon_url)
        time.sleep(5)

        # 페이지 높이에 맞게 조정
        page_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1920, page_height)
        time.sleep(2)

        dacon_path = "screenshots/dacon_competitions.png"
        driver.save_screenshot(dacon_path)
        print(f"[OK] Dacon 스크린샷 저장: {dacon_path}")

        # Kaggle 캡처
        print("\n[2/2] Kaggle 페이지 접속 중...")
        driver.get(kaggle_url)
        time.sleep(5)

        page_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1920, page_height)
        time.sleep(2)

        kaggle_path = "screenshots/kaggle_competitions.png"
        driver.save_screenshot(kaggle_path)
        print(f"[OK] Kaggle 스크린샷 저장: {kaggle_path}")

        return dacon_path, kaggle_path

    except Exception as e:
        print(f"[ERROR] 스크린샷 캡처 실패: {e}")
        return None, None
    finally:
        driver.quit()


def interactive_update():
    """
    대화형 업데이트 프로세스
    사용자가 Claude에게 스크린샷을 보여주고 정보를 추출합니다
    """
    print("\n" + "=" * 60)
    print("Step 2: 이미지 분석 및 정보 추출")
    print("=" * 60)

    print("""
다음 단계를 진행하세요:

1. screenshots/dacon_competitions.png 파일을 Claude Code에 전달
2. Claude에게 다음과 같이 요청:
   "이 Dacon 대회 스크린샷을 분석해서 competitions.json 형식으로
    완료된 대회와 진행중인 대회 목록을 추출해줘"

3. screenshots/kaggle_competitions.png 파일을 Claude Code에 전달
4. 동일하게 Kaggle 대회 정보 추출 요청

5. 추출된 정보로 competitions.json 업데이트

6. python update_readme_simple.py 실행

또는 아래 명령어를 실행하여 수동으로 진행:
    python update_readme_simple.py
""")


def main():
    print("=" * 60)
    print("Auto Competition Updater with Vision AI")
    print("=" * 60)

    # Step 1: 스크린샷 캡처
    dacon_path, kaggle_path = capture_screenshots()

    if not dacon_path or not kaggle_path:
        print("\n[ERROR] 스크린샷 캡처 실패")
        return

    # Step 2: 사용자 안내
    interactive_update()

    print("\n" + "=" * 60)
    print("[OK] 준비 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
