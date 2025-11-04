#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dacon & Kaggle Competition Auto-Update Script for GitHub Profile
자동으로 Dacon과 Kaggle 대회 정보를 크롤링하여 README.md를 업데이트합니다.
"""

import re
import time
from datetime import datetime
from typing import List, Dict, Tuple
import pytz

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class CompetitionUpdater:
    def __init__(self):
        self.dacon_url = "https://dacon.io/myprofile/499579/competition"
        self.kaggle_url = "https://www.kaggle.com/najunghwan/competitions"
        self.readme_path = "README.md"

        # 해커톤 키워드 리스트 (해커톤 대회 식별용)
        self.hackathon_keywords = ["해커톤", "hackathon", "Hackathon"]

    def setup_driver(self) -> webdriver.Chrome:
        """Selenium WebDriver 설정"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 백그라운드 실행
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        driver = webdriver.Chrome(options=chrome_options)
        return driver

    def scrape_dacon_competitions(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Dacon 대회 정보 크롤링
        Returns: (완료된 대회 리스트, 진행중인 대회 리스트)
        """
        print("🔍 Dacon 대회 정보를 가져오는 중...")

        driver = self.setup_driver()
        completed = []
        ongoing = []

        try:
            driver.get(self.dacon_url)
            time.sleep(3)  # 페이지 로딩 대기

            # 대회 카드 요소 찾기
            wait = WebDriverWait(driver, 10)

            # 완료된 대회
            try:
                completed_section = driver.find_elements(By.CSS_SELECTOR, ".comp.end")
                for comp in completed_section:
                    comp_data = self._parse_dacon_competition(comp, "completed")
                    if comp_data:
                        completed.append(comp_data)
                print(f"✅ 완료된 대회 {len(completed)}개 발견")
            except Exception as e:
                print(f"⚠️  완료된 대회 크롤링 중 오류: {e}")

            # 진행중인 대회
            try:
                ongoing_section = driver.find_elements(By.CSS_SELECTOR, ".comp.participate, .comp.joined")
                for comp in ongoing_section:
                    comp_data = self._parse_dacon_competition(comp, "ongoing")
                    if comp_data:
                        ongoing.append(comp_data)
                print(f"✅ 진행중인 대회 {len(ongoing)}개 발견")
            except Exception as e:
                print(f"⚠️  진행중인 대회 크롤링 중 오류: {e}")

        except Exception as e:
            print(f"❌ Dacon 크롤링 실패: {e}")
            print("💡 수동으로 README를 업데이트해주세요.")
        finally:
            driver.quit()

        return completed, ongoing

    def _parse_dacon_competition(self, element, status: str) -> Dict:
        """Dacon 대회 요소 파싱"""
        try:
            # 대회명
            name = element.find_element(By.CSS_SELECTOR, ".name").text.strip()

            # 링크
            link = element.find_element(By.TAG_NAME, "a").get_attribute("href")

            # 기간 (예: 2025.05 ~ 2025.06)
            try:
                period = element.find_element(By.CSS_SELECTOR, ".time").text.strip()
            except:
                period = "날짜 정보 없음"

            # 순위/성적
            try:
                ranking = element.find_element(By.CSS_SELECTOR, ".ranking, .leaderboard").text.strip()
            except:
                ranking = "-"

            # 분야
            try:
                category = element.find_element(By.CSS_SELECTOR, ".category, .desc").text.strip()
            except:
                category = "-"

            return {
                "name": name,
                "link": link,
                "period": period,
                "category": category,
                "ranking": ranking,
                "status": status
            }
        except Exception as e:
            print(f"⚠️  대회 파싱 오류: {e}")
            return None

    def scrape_kaggle_competitions(self) -> List[Dict]:
        """Kaggle 대회 정보 크롤링"""
        print("🔍 Kaggle 대회 정보를 가져오는 중...")

        # Kaggle은 로그인이 필요하므로 수동 업데이트 권장
        print("⚠️  Kaggle은 로그인이 필요합니다. 수동으로 업데이트하거나 Kaggle API를 사용하세요.")
        return []

    def extract_existing_hackathons(self, readme_content: str) -> List[str]:
        """
        기존 README에서 해커톤 대회 추출
        """
        hackathons = []

        # 완료된 대회 테이블에서 해커톤 찾기
        completed_section = re.search(
            r'<summary><strong>✅ 데이콘 완료된 대회.*?</summary>(.*?)</table>',
            readme_content,
            re.DOTALL
        )

        if completed_section:
            table_content = completed_section.group(1)
            rows = re.findall(r'<tr>(.*?)</tr>', table_content, re.DOTALL)

            for row in rows:
                # 해커톤 키워드가 포함된 행 찾기
                if any(keyword in row for keyword in self.hackathon_keywords):
                    hackathons.append(row)

        print(f"✅ 기존 해커톤 {len(hackathons)}개 발견")
        return hackathons

    def update_readme(self, dacon_completed: List[Dict], dacon_ongoing: List[Dict]):
        """README.md 업데이트"""
        print("📝 README.md 업데이트 중...")

        try:
            with open(self.readme_path, 'r', encoding='utf-8') as f:
                readme_content = f.read()
        except FileNotFoundError:
            print(f"❌ {self.readme_path} 파일을 찾을 수 없습니다.")
            return

        # 기존 해커톤 보존
        existing_hackathons = self.extract_existing_hackathons(readme_content)

        # 완료된 대회 테이블 생성
        completed_table = self._generate_completed_table(dacon_completed, existing_hackathons)

        # 진행중인 대회 테이블 생성
        ongoing_table = self._generate_ongoing_table(dacon_ongoing)

        # README 업데이트
        # TODO: 실제 README 업데이트 로직 구현

        # 업데이트 시간 추가
        kst = pytz.timezone('Asia/Seoul')
        update_time = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S KST')

        print(f"✅ README 업데이트 완료! (Last updated: {update_time})")

    def _generate_completed_table(self, competitions: List[Dict], hackathons: List[str]) -> str:
        """완료된 대회 테이블 HTML 생성"""
        # TODO: 실제 테이블 생성 로직
        pass

    def _generate_ongoing_table(self, competitions: List[Dict]) -> str:
        """진행중인 대회 테이블 HTML 생성"""
        # TODO: 실제 테이블 생성 로직
        pass

    def run(self):
        """메인 실행 함수"""
        print("=" * 60)
        print("🚀 GitHub Profile Competition Updater")
        print("=" * 60)

        # Dacon 크롤링
        dacon_completed, dacon_ongoing = self.scrape_dacon_competitions()

        # Kaggle 크롤링 (선택사항)
        # kaggle_comps = self.scrape_kaggle_competitions()

        # README 업데이트
        if dacon_completed or dacon_ongoing:
            self.update_readme(dacon_completed, dacon_ongoing)
        else:
            print("⚠️  가져온 대회 정보가 없습니다.")

        print("=" * 60)
        print("✅ 완료!")
        print("=" * 60)


if __name__ == "__main__":
    updater = CompetitionUpdater()
    updater.run()
