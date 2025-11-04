#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개선된 원클릭 자동 업데이트 시스템 (모듈화된 에이전트 구조)

Agent 1: Screenshot Capture
Agent 2: Vision AI Analysis
Agent 3: Data Validation & Statistics
Agent 4: README Generation
Agent 5: Git Operations
"""

import subprocess
import sys
import os
from datetime import datetime
import pytz
import json

class UpdateAgent:
    """Base class for update agents"""

    def __init__(self, name):
        self.name = name

    def log(self, message, level="INFO"):
        """로그 출력"""
        prefix = {
            "INFO": "[INFO]",
            "OK": "[OK]",
            "ERROR": "[ERROR]",
            "WARN": "[WARN]",
            "AGENT": f"[AGENT: {self.name}]"
        }
        print(f"{prefix.get(level, '[LOG]')} {message}")

    def run_command(self, command, description):
        """명령어 실행"""
        self.log(f"{description}...", "AGENT")
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            self.log(f"{description} completed!", "OK")
            if result.stdout:
                print(result.stdout)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            self.log(f"{description} failed!", "ERROR")
            if e.stdout:
                print(f"Output: {e.stdout}")
            if e.stderr:
                print(f"Error: {e.stderr}")
            return False, None
        except Exception as e:
            self.log(f"Unexpected error: {e}", "ERROR")
            return False, None

class ScreenshotAgent(UpdateAgent):
    """Agent 1: 스크린샷 캡처"""

    def __init__(self):
        super().__init__("Screenshot Capture")

    def execute(self):
        """스크린샷 캡처 실행"""
        self.log("Starting screenshot capture...", "AGENT")
        success, _ = self.run_command(
            "python auto_update.py",
            "Capturing Dacon and Kaggle screenshots"
        )
        if success:
            # 스크린샷 파일 확인
            dacon_exists = os.path.exists("screenshots/dacon_competitions.png")
            kaggle_exists = os.path.exists("screenshots/kaggle_competitions.png")

            if dacon_exists and kaggle_exists:
                self.log("Screenshots captured successfully!", "OK")
                return True
            else:
                self.log("Screenshot files not found!", "ERROR")
                return False
        return False

class VisionAIAgent(UpdateAgent):
    """Agent 2: Vision AI 분석"""

    def __init__(self):
        super().__init__("Vision AI Analysis")

    def execute(self):
        """Vision AI 분석 실행"""
        self.log("Starting Vision AI analysis...", "AGENT")

        # API 키 확인
        if not os.environ.get('ANTHROPIC_API_KEY'):
            self.log("ANTHROPIC_API_KEY not found!", "ERROR")
            return False

        success, output = self.run_command(
            "python analyze_screenshots_v2.py",
            "Analyzing screenshots with Vision AI"
        )

        if success:
            # competitions.json 생성 확인
            if os.path.exists("competitions.json"):
                self.log("Analysis completed and JSON updated!", "OK")
                return True
            else:
                self.log("competitions.json not created!", "ERROR")
                return False
        return False

class ValidationAgent(UpdateAgent):
    """Agent 3: 데이터 검증"""

    def __init__(self):
        super().__init__("Data Validation")

    def execute(self):
        """데이터 검증"""
        self.log("Validating extracted data...", "AGENT")

        try:
            with open('competitions.json', 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 기본 구조 확인
            if 'dacon' not in data or 'kaggle' not in data:
                self.log("Invalid data structure!", "ERROR")
                return False

            # Dacon 데이터 확인
            dacon = data['dacon']
            if 'completed' not in dacon or 'ongoing' not in dacon:
                self.log("Missing Dacon competition data!", "ERROR")
                return False

            # Kaggle 데이터 확인
            kaggle = data['kaggle']
            if isinstance(kaggle, dict):
                if 'completed' not in kaggle:
                    self.log("Missing Kaggle competition data!", "ERROR")
                    return False

            # 통계 확인
            if 'achievements' not in dacon:
                self.log("Missing achievements statistics!", "ERROR")
                return False

            # 요약 출력
            self.log("=" * 60)
            self.log(f"Dacon Completed: {len(dacon['completed'])} competitions")
            self.log(f"Dacon Ongoing: {len(dacon['ongoing'])} competitions")
            self.log(f"Kaggle Completed: {len(kaggle['completed']) if isinstance(kaggle, dict) else len(kaggle)} competitions")
            self.log(f"Achievements: {dacon['achievements']}")
            self.log("=" * 60)

            self.log("Data validation passed!", "OK")
            return True

        except FileNotFoundError:
            self.log("competitions.json not found!", "ERROR")
            return False
        except json.JSONDecodeError:
            self.log("Invalid JSON format!", "ERROR")
            return False
        except Exception as e:
            self.log(f"Validation error: {e}", "ERROR")
            return False

class READMEAgent(UpdateAgent):
    """Agent 4: README 생성"""

    def __init__(self):
        super().__init__("README Generation")

    def execute(self):
        """README 업데이트"""
        self.log("Generating README...", "AGENT")
        success, _ = self.run_command(
            "python update_readme_simple.py",
            "Updating README.md"
        )

        if success:
            # README.md 파일 확인
            if os.path.exists("README.md"):
                self.log("README generated successfully!", "OK")
                return True
            else:
                self.log("README.md not found!", "ERROR")
                return False
        return False

class GitAgent(UpdateAgent):
    """Agent 5: Git 작업"""

    def __init__(self):
        super().__init__("Git Operations")

    def execute(self):
        """Git 커밋 및 푸시"""
        self.log("Committing changes to Git...", "AGENT")

        # Git add
        self.run_command("git add .", "Adding files to git")

        # 변경사항 확인
        success, status = self.run_command("git status --short", "Checking git status")
        if not success or not status or status.strip() == "":
            self.log("No changes to commit", "WARN")
            return True

        # Git commit
        kst = pytz.timezone('Asia/Seoul')
        commit_time = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S KST')

        commit_message = f"""Auto-update: competitions data and README - {commit_time}

Updated with improved one-click automation system:
- Captured latest Dacon and Kaggle screenshots
- Analyzed with Vision AI (enhanced prompts)
- Auto-calculated achievement statistics
- Preserved hackathons and code links
- Timestamp: {commit_time}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""

        # Windows에서 heredoc 대신 파일 사용
        with open('temp_commit_msg.txt', 'w', encoding='utf-8') as f:
            f.write(commit_message)

        commit_cmd = 'git commit -F temp_commit_msg.txt'

        success, _ = self.run_command(commit_cmd, "Committing to git")

        # 임시 파일 삭제
        if os.path.exists('temp_commit_msg.txt'):
            os.remove('temp_commit_msg.txt')

        if not success:
            self.log("Git commit failed (maybe no changes?)", "WARN")
            return False

        # Git push
        success, _ = self.run_command("git push", "Pushing to GitHub")

        if success:
            self.log("Changes pushed to GitHub!", "OK")
            return True
        else:
            self.log("Git push failed! You may need to push manually.", "WARN")
            return False

def main():
    """메인 실행 함수"""
    print("\n" + "=" * 60)
    print("IMPROVED ONE-CLICK AUTO UPDATE SYSTEM")
    print("Modular Agent Architecture")
    print("=" * 60)
    kst = pytz.timezone('Asia/Seoul')
    start_time = datetime.now(kst)
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
    print("=" * 60 + "\n")

    # 에이전트 초기화
    agents = [
        ScreenshotAgent(),       # Agent 1
        VisionAIAgent(),         # Agent 2
        ValidationAgent(),       # Agent 3
        READMEAgent(),          # Agent 4
        GitAgent()              # Agent 5
    ]

    # 에이전트 순차 실행
    for i, agent in enumerate(agents, 1):
        print(f"\n{'='*60}")
        print(f"STEP {i}/5: {agent.name}")
        print('='*60)

        success = agent.execute()

        if not success:
            print(f"\n{'='*60}")
            print(f"[ABORT] {agent.name} failed!")
            print(f"Please check the error messages above.")
            print('='*60)

            # Git 에이전트는 실패해도 계속 진행
            if i < 5:
                sys.exit(1)

    # 완료
    end_time = datetime.now(kst)
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 60)
    print("[OK] ONE-CLICK UPDATE COMPLETED!")
    print("=" * 60)
    print(f"Finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
    print(f"Total duration: {duration:.1f} seconds")
    print("\nYour GitHub profile has been updated!")
    print("Visit: https://github.com/shaun0927/shaun0927")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
