#!/usr/bin/env bash
# Regression tests for ../safety-guards.sh.
# Run: bash plugins/base/hooks/tests/test_safety_guards.sh
# Each case pipes one command into the hook as Claude Code's PreToolUse JSON and
# checks the verdict:
#   block - exit 2 (command refused)
#   deny  - exit 0 with permissionDecision "deny" (push without a token)
#   allow - exit 0 without a deny
# Everything runs inside one temp folder with its own HOME and git repo; no real
# command from the cases is ever executed.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")/.." && pwd)/safety-guards.sh"
WORK=$(mktemp -d)
trap 'rm -r "$WORK"' EXIT
git -C "$WORK" init -q repo
cd "$WORK/repo"

PASS=0 FAIL=0
check() {
  local want=$1 cmd=$2 out rc got
  out=$(printf '%s' "$cmd" |
    python3 -c 'import json,sys; print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.stdin.read()}}))' |
    HOME="$WORK" bash "$HOOK" 2>/dev/null)
  rc=$?
  if [ "$rc" = 2 ]; then got=block
  elif [[ $out == *'"permissionDecision"'*'"deny"'* ]]; then got=deny
  else got=allow
  fi
  if [ "$got" = "$want" ]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    printf 'FAIL want=%s got=%s: %s\n' "$want" "$got" "$cmd"
  fi
}

# rm -rf on home or root: blocked, whatever the username or flag form
check block 'rm -rf ~'
check block 'rm -rf ~/'
check block 'rm -rf ~/projects/old'
check block 'rm -fr ~/'
check block 'rm -r -f "$HOME"'
check block 'rm --recursive --force ${HOME}/x'
check block 'rm -rf /home/sam/'
check block 'rm -rf /home/nagel'
check block 'rm -rf /Users/sam/Documents'
check block 'rm -rf /'
check block 'rm -rf /*'
check block 'rm -rf /usr'
check block 'sudo rm -rf /etc'
check block 'cd /tmp && rm -rf ~/x'
check block 'bash -c "rm -rf ~"'
check block 'echo $(rm -rf /home/sam)'

# rm -rf elsewhere, or rm without both flags: allowed
check allow 'rm -rf /tmp/tmp.abc123'
check allow 'D=$(mktemp -d) && cd /home/sam/project && rm -rf "$D"'
check allow 'rm -rf node_modules dist'
check allow 'rm -r ~/x'
check allow 'rm -f ~/x.log'
check allow 'git commit -m "chore: stop using rm -rf ~/ in docs"'
check allow 'grep -rn "rm -rf /" docs'

# .env: writes blocked, reads and example files allowed
check block 'echo X=1 > .env'
check block 'printf "A=b\n" >> config/.env.local'
check block 'cp tmp .env'
check block 'mv new.env .env.production'
check block 'tee .env < tmp'
check block 'sed -i s/a/b/ .env'
check allow 'cat .env'
check allow 'grep KEY .env'
check allow 'cat .env.example'
check allow 'cp .env.example .env.sample'
check allow 'echo X=1 > .env.example'
check allow 'npm test > /dev/null && grep -r process.env src'
check allow 'cp .env backup.txt'

# Hardcoded secrets: still blocked
check block 'export API_KEY=abcdefghijklmnop1234'

# Push gate (unchanged): force push blocked, push without a token denied
check block 'git push --force origin main'
check block 'git push origin +main'
check deny 'git push origin main'
check allow 'git commit -m "docs: explain git push"'

printf '%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" = 0 ]
