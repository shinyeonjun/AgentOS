param(
  [string]$CodexHome = "",
  [string]$ServerName = "agentos",
  [string]$Launcher = "",
  [string]$Cwd = "",
  [switch]$DryRun,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $ScriptDir "setup-codex-mcp.cjs"
$ArgsList = @($SetupScript, "--server-name", $ServerName)

if ($CodexHome) { $ArgsList += @("--codex-home", $CodexHome) }
if ($Launcher) { $ArgsList += @("--launcher", $Launcher) }
if ($Cwd) { $ArgsList += @("--cwd", $Cwd) }
if ($DryRun) { $ArgsList += "--dry-run" }
if ($Force) { $ArgsList += "--force" }

node @ArgsList
