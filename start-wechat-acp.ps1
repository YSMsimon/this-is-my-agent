$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
$config = Get-Content "wechat-acp.config.json" | ConvertFrom-Json
npx wechat-acp --agent $config.agent --cwd $config.cwd
