[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$ClientToken,

  [string]$ApiBase = "https://api-ariusmonitor.flagee.cloud/api/ingest",
  [string]$ImageName = "ghcr.io/flagee-cloud/flageemonitor-client:latest",
  [string]$RuntimeName = "flageemonitor",
  [string]$ContainerRoot = "/flageemonitor",
  [string]$GhcrUser,
  [string]$GhcrToken
)

$ErrorActionPreference = "Stop"

function Assert-Command($Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Comando '$Name' nao encontrado."
  }
}

Assert-Command docker
Assert-Command Invoke-RestMethod

try {
  docker info | Out-Null
}
catch {
  throw "Nao foi possivel acessar o daemon Docker."
}

if (($GhcrUser -and -not $GhcrToken) -or ($GhcrToken -and -not $GhcrUser)) {
  throw "GHCR_USER e GHCR_TOKEN devem ser informados juntos."
}

$baseDir = Join-Path $env:ProgramData "FlageeMonitor"
$configDir = Join-Path $baseDir "config"
$dataDir = Join-Path $baseDir "data"
$logsDir = Join-Path $dataDir "logs"
$utilitiesDir = Join-Path $dataDir "utilities"
$binDir = Join-Path $baseDir "bin"

$configPath = Join-Path $configDir "config_bot.json"
$envPath = Join-Path $configDir "flageemonitor.env"
$ghcrEnvPath = Join-Path $configDir "ghcr.env"

$configUrl = "$ApiBase/bot/config"

New-Item -ItemType Directory -Force -Path $configDir, $dataDir, $logsDir, $utilitiesDir, $binDir | Out-Null

Write-Host "Baixando config_bot.json..."
$headers = @{ "X-Bot-Token" = $ClientToken }
Invoke-RestMethod -Uri $configUrl -Headers $headers -Method Get | ConvertTo-Json -Depth 20 | Set-Content -Path $configPath -Encoding UTF8

$config = Get-Content $configPath -Raw | ConvertFrom-Json
if (-not $config.PARAM_REDE) {
  throw "config_bot.json sem PARAM_REDE."
}

$timezone = if ($config.TIMEZONE) { $config.TIMEZONE } else { "America/Sao_Paulo" }

@(
  "FLAGEEMONITOR_REDE=\"$($config.PARAM_REDE)\"",
  "FLAGEEMONITOR_TOKEN=\"$ClientToken\"",
  "FLAGEEMONITOR_API_BASE=\"$ApiBase\"",
  "FLAGEEMONITOR_CONFIG_URL=\"$configUrl\"",
  "FLAGEEMONITOR_IMAGE=\"$ImageName\"",
  "FLAGEEMONITOR_CONFIG_PATH=\"$ContainerRoot/config_bot.json\"",
  "FLAGEEMONITOR_CONTAINER_ROOT=\"$ContainerRoot\"",
  "TZ=\"$timezone\""
) | Set-Content -Path $envPath -Encoding UTF8

if ($GhcrUser -and $GhcrToken) {
  @(
    "GHCR_USER=\"$GhcrUser\"",
    "GHCR_TOKEN=\"$GhcrToken\""
  ) | Set-Content -Path $ghcrEnvPath -Encoding UTF8
}

if ($GhcrUser -and $GhcrToken) {
  $GhcrToken | docker login ghcr.io -u $GhcrUser --password-stdin | Out-Null
}

docker pull $ImageName | Out-Null

$mountConfig = "${configPath}:${ContainerRoot}/config_bot.json:ro"
$mountLogs = "${logsDir}:${ContainerRoot}/logs"
$mountUtilities = "${utilitiesDir}:${ContainerRoot}/utilities:ro"

$existing = docker ps -aq -f "name=^${RuntimeName}$"
if ($existing) {
  docker rm -f $RuntimeName | Out-Null
}

docker run -d --name $RuntimeName --restart unless-stopped `
  --env-file $envPath `
  -e "RUN_MODE=daemon" `
  -v $mountConfig `
  -v $mountLogs `
  -v $mountUtilities `
  $ImageName | Out-Null

$runScript = @"
param([Parameter(ValueFromRemainingArguments = `$true)][string[]]`$Args)
docker exec $RuntimeName ${ContainerRoot}/run_action.sh @Args
"@
$runPath = Join-Path $binDir "flageemonitor-run.ps1"
Set-Content -Path $runPath -Value $runScript -Encoding UTF8

$logsScript = "docker logs -f $RuntimeName"
$logsPath = Join-Path $binDir "flageemonitor-logs.ps1"
Set-Content -Path $logsPath -Value $logsScript -Encoding UTF8

Write-Host "Instalacao concluida."
Write-Host "Container: $RuntimeName"
Write-Host "Wrappers: $runPath | $logsPath"
