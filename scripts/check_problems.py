#!/usr/bin/env python3
"""Antigravity Lifecycle Hook & CLI: 自動で Pyrefly 等の型・診断エラーをチェックするスクリプト。

エージェント停止時 (Stop hook) に呼ばれた場合、エラーが残っていれば
{"decision": "continue", "reason": "..."} を返し、エージェントに自動修正を促す。
"""

import json
import subprocess
import sys


def main() -> None:
    # stdin から hook 入力を読み込み（渡されない場合は空辞書）
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read().strip()
            if raw:
                json.loads(raw)
        except Exception:
            pass

    # Pyrefly check の実行
    cmd = [
        "uvx",
        "pyrefly",
        "check",
        "--check-unannotated-defs",
        "--min-severity",
        "warn",
        "--output-format=full-text",
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if proc.returncode == 0:
        # 問題なし
        print(json.dumps({}))
        sys.exit(0)

    # 問題が検出された場合
    error_output = proc.stdout.strip()
    response = {
        "decision": "continue",
        "reason": (
            "Pyrefly diagnostics / type check errors detected in src or tests. "
            "Please fix these problems automatically before finishing:\n\n"
            f"{error_output}"
        ),
    }
    print(json.dumps(response, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
