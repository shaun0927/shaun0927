#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vision AI 기반 대회 정보 자동 업데이트 스크립트
스크린샷을 캡처하고 Claude에게 전달하여 대회 정보를 추출합니다.
"""

import json
import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pytz


class CompetitionScreenshotUpdater:
    def __init__(self):
        self.dacon_url = "https://dacon.io/myprofile/499579/competition"
        self.kaggle_url = "https://www.kaggle.com/najunghwan/competitions"
        self.screenshot_dir = "screenshots"

        # 스크린샷 디렉토리 생성
        os.makedirs(self.screenshot_dir, exist_ok=True)

    def setup_driver(self):
        """Selenium WebDriver 설정"""
        chrome_options = Options()
        # 헤드리스 모드 (백그라운드 실행)
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        driver = webdriver.Chrome(options=chrome_options)
        return driver

    def capture_dacon_screenshot(self):
        """Dacon 대회 페이지 스크린샷 캡처"""
        print("[INFO] Dacon 페이지 스크린샷 캡처 중...")

        driver = self.setup_driver()
        screenshot_path = os.path.join(self.screenshot_dir, "dacon_competitions.png")

        try:
            driver.get(self.dacon_url)
            time.sleep(5)  # 페이지 로딩 대기

            # 전체 페이지 스크린샷
            driver.save_screenshot(screenshot_path)
            print(f"[OK] 스크린샷 저장: {screenshot_path}")

            return screenshot_path

        except Exception as e:
            print(f"[ERROR] Dacon 스크린샷 실패: {e}")
            return None
        finally:
            driver.quit()

    def capture_kaggle_screenshot(self):
        """Kaggle 대회 페이지 스크린샷 캡처"""
        print("[INFO] Kaggle 페이지 스크린샷 캡처 중...")

        driver = self.setup_driver()
        screenshot_path = os.path.join(self.screenshot_dir, "kaggle_competitions.png")

        try:
            driver.get(self.kaggle_url)
            time.sleep(5)  # 페이지 로딩 대기

            # 전체 페이지 스크린샷
            driver.save_screenshot(screenshot_path)
            print(f"[OK] 스크린샷 저장: {screenshot_path}")

            return screenshot_path

        except Exception as e:
            print(f"[ERROR] Kaggle 스크린샷 실패: {e}")
            return None
        finally:
            driver.quit()

    def analyze_with_claude(self, screenshot_path, platform):
        """
        스크린샷을 Claude에게 전달하여 대회 정보 추출

        이 함수는 실제로 Claude Code의 Task agent를 사용하거나,
        사용자가 수동으로 이미지를 확인하고 정보를 입력하는 방식으로 구현됩니다.
        """
        print(f"[INFO] {platform} 스크린샷 분석 준비 완료")
        print(f"[INFO] 스크린샷 경로: {screenshot_path}")
        print(f"\n{'='*60}")
        print(f"다음 단계:")
        print(f"1. {screenshot_path} 파일을 확인하세요")
        print(f"2. Claude에게 이미지를 보여주고 대회 정보를 추출하도록 요청하세요")
        print(f"3. 추출된 정보를 competitions.json에 반영하세요")
        print(f"{'='*60}\n")

        return None

    def run(self):
        """메인 실행 함수"""
        print("=" * 60)
        print("Competition Screenshot Updater")
        print("=" * 60)

        # 1. Dacon 스크린샷 캡처
        dacon_screenshot = self.capture_dacon_screenshot()
        if dacon_screenshot:
            self.analyze_with_claude(dacon_screenshot, "Dacon")

        # 2. Kaggle 스크린샷 캡처
        kaggle_screenshot = self.capture_kaggle_screenshot()
        if kaggle_screenshot:
            self.analyze_with_claude(kaggle_screenshot, "Kaggle")

        print("\n" + "=" * 60)
        print("[OK] 스크린샷 캡처 완료!")
        print("[TIP] 스크린샷을 확인하고 competitions.json을 업데이트하세요")
        print("=" * 60)


if __name__ == "__main__":
    updater = CompetitionScreenshotUpdater()
    updater.run()
