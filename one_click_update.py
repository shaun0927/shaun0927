#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
원클릭 자동 업데이트 스크립트
스크린샷 캡처 -> AI 분석 -> README 업데이트 -> Git 커밋/푸시 모두 자동화
"""

import subprocess
import sys
import os
from datetime import datetime
import pytz

def run_command(command, description):
    """명령어 실행"""
    print(f"\n[INFO] {description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print(f"[OK] {description} completed!")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {description} failed!")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

def check_api_key():
    """API 키 확인"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n" + "=" * 60)
        print("[ERROR] ANTHROPIC_API_KEY not found!")
        print("=" * 60)
        print("\nPlease set your API key using one of these methods:")
        print("\n1. Temporary (current session):")
        print("   set ANTHROPIC_API_KEY=your_key_here")
        print("\n2. Permanent (system environment variable):")
        print("   - Search 'environment variables' in Windows")
        print("   - Add new system variable: ANTHROPIC_API_KEY")
        print("\n3. Using .env file (create .env in this directory):")
        print("   ANTHROPIC_API_KEY=your_key_here")
        print("=" * 60)
        return False
    print("[OK] API key found!")
    return True

def main():
    print("=" * 60)
    print("ONE-CLICK AUTO UPDATE SYSTEM")
    print("=" * 60)
    print(f"Started at: {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S KST')}")
    print("=" * 60)

    # 1. API 키 확인
    if not check_api_key():
        sys.exit(1)

    # 2. 스크린샷 캡처
    if not run_command("python auto_update.py", "Step 1/5: Capturing screenshots"):
        print("\n[ABORT] Screenshot capture failed!")
        sys.exit(1)

    # 3. AI 스크린샷 분석
    if not run_command("python analyze_screenshots.py", "Step 2/5: Analyzing screenshots with AI"):
        print("\n[ABORT] Screenshot analysis failed!")
        sys.exit(1)

    # 4. README 업데이트
    if not run_command("python update_readme_simple.py", "Step 3/5: Updating README"):
        print("\n[ABORT] README update failed!")
        sys.exit(1)

    # 5. Git 커밋
    print("\n[INFO] Step 4/5: Committing changes to git...")

    # Git add
    if not run_command("git add .", "Adding files to git"):
        print("[WARN] Git add failed, but continuing...")

    # Git commit
    kst = pytz.timezone('Asia/Seoul')
    commit_time = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S KST')

    commit_message = f"""Update competitions data and README - {commit_time}

Auto-updated with one-click automation system:
- Captured latest Dacon and Kaggle screenshots
- Analyzed competition data with Vision AI
- Updated competitions.json and README.md
- Timestamp: {commit_time}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""

    # Windows에서 heredoc 대신 파일 사용
    with open('temp_commit_msg.txt', 'w', encoding='utf-8') as f:
        f.write(commit_message)

    commit_cmd = 'git commit -F temp_commit_msg.txt'

    if run_command(commit_cmd, "Committing to git"):
        # 임시 파일 삭제
        if os.path.exists('temp_commit_msg.txt'):
            os.remove('temp_commit_msg.txt')
        print("[OK] Git commit successful!")
    else:
        print("[WARN] Git commit failed (maybe no changes?)")
        if os.path.exists('temp_commit_msg.txt'):
            os.remove('temp_commit_msg.txt')

    # 6. Git push
    if not run_command("git push", "Step 5/5: Pushing to GitHub"):
        print("[WARN] Git push failed! You may need to push manually.")

    print("\n" + "=" * 60)
    print("[OK] ONE-CLICK UPDATE COMPLETED!")
    print("=" * 60)
    print(f"Finished at: {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S KST')}")
    print("\nYour GitHub profile has been updated!")
    print("Visit: https://github.com/shaun0927/shaun0927")
    print("=" * 60)

if __name__ == "__main__":
    main()
