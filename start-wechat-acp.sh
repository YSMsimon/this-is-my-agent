#!/bin/bash
cd "$(dirname "$0")"
AGENT=$(python3 -c "import json; c=json.load(open('wechat-acp.config.json')); print(c['agent'])")
CWD=$(python3 -c "import json; c=json.load(open('wechat-acp.config.json')); print(c['cwd'])")
npx wechat-acp --agent "$AGENT" --cwd "$CWD"
