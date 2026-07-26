# One-command Azure Container Apps deploy (backend + frontend).
#
# IMPORTANT: This script does NOT use ACR Tasks (az acr build / --source).
# Many Azure subscriptions block ACR Tasks (TasksOperationsNotAllowed).
# Instead it: local Docker build -> docker push -> containerapp create/update.
#
# Prerequisites:
#   - Azure CLI (az) logged in
#   - Docker Desktop running (Linux containers)
#   - Root .env with API keys
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1
#
# Optional:
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1 -SubscriptionId "<id>"
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1 -BackendOnly
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1 -FrontendOnly

[CmdletBinding()]
param(
    [string]$SubscriptionId = "",
    [string]$Location = "eastus",
    [string]$ResourceGroup = "rg-release-assurance",
    [string]$EnvironmentName = "cae-release-assurance",
    [string]$BackendName = "ca-release-assurance-api",
    [string]$FrontendName = "ca-release-assurance-web",
    [string]$AcrName = "",
    [string]$EnvFile = "",
    [int]$MinReplicas = 0,
    [int]$MaxReplicas = 3,
    [string]$BackendCpu = "1.0",
    [string]$BackendMemory = "2Gi",
    [string]$FrontendCpu = "0.5",
    [string]$FrontendMemory = "1Gi",
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$SkipLogin,
    [switch]$SkipScale
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not $EnvFile) {
    $EnvFile = Join-Path $RepoRoot ".env"
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ("==> " + $Message) -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host ("    " + $Message) -ForegroundColor Green
}

function Write-WarnLine {
    param([string]$Message)
    Write-Host ("    " + $Message) -ForegroundColor Yellow
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw ("Required command not found: " + $Name)
    }
}

function Import-DotEnv {
    param([string]$Path)
    $map = @{}
    if (-not (Test-Path $Path)) {
        throw ("Env file not found: " + $Path + ". Copy .env.example to .env and fill API keys.")
    }
    Get-Content -Path $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        $map[$key] = $val
    }
    return $map
}

function Get-EnvOrDefault {
    param($Map, [string]$Key, [string]$Default = "")
    if ($Map.ContainsKey($Key) -and $null -ne $Map[$Key] -and ("{0}" -f $Map[$Key]).Trim() -ne "") {
        return ("{0}" -f $Map[$Key]).Trim()
    }
    return $Default
}

function Invoke-AzQuiet {
    # Run az without treating stderr "ResourceNotFound" as a terminating PowerShell error.
    # With $ErrorActionPreference=Stop, az native stderr becomes NativeCommandError and aborts.
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$AzArgs
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & az @AzArgs 2>$null
        return @{
            ExitCode = $LASTEXITCODE
            Output   = $output
            Text     = if ($null -eq $output) { "" } else { ("{0}" -f $output).Trim() }
        }
    }
    finally {
        $ErrorActionPreference = $prev
    }
}

function Ensure-Provider {
    param([string]$Namespace)
    $probe = Invoke-AzQuiet -AzArgs @("provider", "show", "--namespace", $Namespace, "--query", "registrationState", "-o", "tsv")
    $state = $probe.Text
    if ($state -eq "Registered") {
        Write-Ok ($Namespace + " already Registered")
        return
    }
    Write-WarnLine ("Registering " + $Namespace + " (state=" + $state + ")...")
    az provider register --namespace $Namespace --wait | Out-Null
    $probe2 = Invoke-AzQuiet -AzArgs @("provider", "show", "--namespace", $Namespace, "--query", "registrationState", "-o", "tsv")
    $state = $probe2.Text
    if ($state -ne "Registered") {
        throw ("Failed to register provider " + $Namespace + " (state=" + $state + ")")
    }
    Write-Ok ($Namespace + " Registered")
}

function Test-ContainerAppExists {
    param([string]$Name, [string]$Rg)
    # Prefer list+filter so missing apps never hit ResourceNotFound stderr
    $probe = Invoke-AzQuiet -AzArgs @(
        "containerapp", "list",
        "--resource-group", $Rg,
        "--query", ("[?name=='{0}'].id | [0]" -f $Name),
        "-o", "tsv"
    )
    if ($probe.Text) { return $true }

    $show = Invoke-AzQuiet -AzArgs @(
        "containerapp", "show",
        "--name", $Name,
        "--resource-group", $Rg,
        "--query", "id",
        "-o", "tsv"
    )
    return [bool]$show.Text
}

function Get-ContainerAppUrl {
    param([string]$Name, [string]$Rg)
    $probe = Invoke-AzQuiet -AzArgs @(
        "containerapp", "show",
        "--name", $Name,
        "--resource-group", $Rg,
        "--query", "properties.configuration.ingress.fqdn",
        "-o", "tsv"
    )
    $fqdn = $probe.Text
    if (-not $fqdn) {
        throw ("Could not resolve FQDN for container app " + $Name + ". Did deploy succeed?")
    }
    return ("https://" + $fqdn)
}

function Get-AcrCredentials {
    param([string]$RegistryName)
    az acr update --name $RegistryName --admin-enabled true | Out-Null
    $json = az acr credential show --name $RegistryName -o json
    if ($LASTEXITCODE -ne 0 -or -not $json) {
        throw ("Failed to read ACR credentials for " + $RegistryName + ". Check RBAC (AcrPush / Owner).")
    }
    $creds = $json | ConvertFrom-Json
    $password = $null
    if ($creds.passwords -and $creds.passwords.Count -gt 0) {
        $password = $creds.passwords[0].value
    }
    if (-not $password) {
        throw ("ACR admin password empty for " + $RegistryName + ". Enable admin user in Azure Portal > ACR > Access keys.")
    }
    return @{
        Username = $creds.username
        Password = $password
        Server   = ($RegistryName + ".azurecr.io")
    }
}

function Connect-AcrDocker {
    param(
        [string]$RegistryName,
        [hashtable]$AcrCreds
    )
    # Method 1 (preferred on Windows): Azure CLI exchanges AAD token for Docker login
    Write-Ok ("az acr login --name " + $RegistryName)
    az acr login --name $RegistryName
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "az acr login succeeded"
        return
    }

    Write-WarnLine "az acr login failed; trying admin user docker login..."
    # Method 2: admin user + password-stdin (avoid echoing password)
    $loginOk = $false
    try {
        $AcrCreds.Password | & docker login $AcrCreds.Server --username $AcrCreds.Username --password-stdin 2>&1 | ForEach-Object { Write-Host ("    " + $_) }
        if ($LASTEXITCODE -eq 0) { $loginOk = $true }
    }
    catch {
        Write-WarnLine ("docker login stdin failed: " + $_.Exception.Message)
    }

    if (-not $loginOk) {
        # Method 3: explicit password flag (last resort; some Docker Desktop builds mishandle stdin)
        Write-WarnLine "Retrying docker login with --password..."
        & docker login $AcrCreds.Server --username $AcrCreds.Username --password $AcrCreds.Password 2>&1 | ForEach-Object { Write-Host ("    " + $_) }
        if ($LASTEXITCODE -eq 0) { $loginOk = $true }
    }

    if (-not $loginOk) {
        $msg = @(
            ("Docker could not log in to ACR " + $AcrCreds.Server + ".")
            "Fix checklist:"
            ("1. Portal > Container registries > " + $RegistryName + " > Access keys > Admin user = Enabled")
            "2. Role AcrPush / Contributor / Owner on the registry"
            "3. Docker Desktop running Linux containers"
            ("4. Manual test: az acr login --name " + $RegistryName)
            ("5. Then: docker push " + $AcrCreds.Server + "/hello:test")
        ) -join [Environment]::NewLine
        throw $msg
    }
    Write-Ok "docker login (admin) succeeded"
}

function Ensure-Acr {
    param(
        [string]$Rg,
        [string]$Loc,
        [string]$PreferredName
    )
    $existingProbe = Invoke-AzQuiet -AzArgs @("acr", "list", "--resource-group", $Rg, "--query", "[0].name", "-o", "tsv")
    $existing = $existingProbe.Text
    if ($existing) {
        Write-Ok ("Using existing ACR: " + $existing)
        return $existing
    }

    $name = $PreferredName
    if (-not $name) {
        # ACR names: 5-50 alphanumeric, globally unique
        $suffix = -join ((48..57) + (97..122) | Get-Random -Count 8 | ForEach-Object { [char]$_ })
        $name = ("ra" + $suffix)
    }

    Write-WarnLine ("Creating ACR: " + $name)
    az acr create `
        --name $name `
        --resource-group $Rg `
        --location $Loc `
        --sku Basic `
        --admin-enabled true | Out-Null
    Write-Ok ("Created ACR: " + $name)
    return $name
}

function Ensure-ContainerAppEnvironment {
    param(
        [string]$Name,
        [string]$Rg,
        [string]$Loc
    )
    $envProbe = Invoke-AzQuiet -AzArgs @(
        "containerapp", "env", "show",
        "--name", $Name,
        "--resource-group", $Rg,
        "--query", "name",
        "-o", "tsv"
    )
    if ($envProbe.Text) {
        Write-Ok ("Environment exists: " + $Name)
        return
    }
    Write-WarnLine ("Creating Container Apps environment: " + $Name)
    az containerapp env create `
        --name $Name `
        --resource-group $Rg `
        --location $Loc | Out-Null
    Write-Ok ("Created environment: " + $Name)
}

function Invoke-DockerBuildPush {
    param(
        [string]$Image,
        [string]$Dockerfile,
        [string]$Context,
        [hashtable]$BuildArgs = @{},
        [string]$RegistryName = "",
        [hashtable]$AcrCreds = $null
    )
    $argList = @(
        "build",
        "--platform", "linux/amd64",
        "-f", $Dockerfile,
        "-t", $Image
    )
    foreach ($k in $BuildArgs.Keys) {
        $argList += "--build-arg"
        $argList += ("{0}={1}" -f $k, $BuildArgs[$k])
    }
    $argList += $Context

    Write-Ok ("docker build " + $Image)
    & docker @argList
    if ($LASTEXITCODE -ne 0) {
        throw ("docker build failed for " + $Image)
    }

    # Re-auth right before push (Docker Desktop sometimes drops ACR creds)
    if ($RegistryName -and $AcrCreds) {
        Connect-AcrDocker -RegistryName $RegistryName -AcrCreds $AcrCreds
    }

    Write-Ok ("docker push " + $Image)
    $pushOut = & docker push $Image 2>&1
    $pushOut | ForEach-Object { Write-Host ("    " + $_) }
    if ($LASTEXITCODE -ne 0) {
        $joined = ($pushOut | Out-String)
        # One automatic re-login + retry
        if ($RegistryName -and $AcrCreds) {
            Write-WarnLine "Push failed; re-login and retry once..."
            Connect-AcrDocker -RegistryName $RegistryName -AcrCreds $AcrCreds
            $pushOut2 = & docker push $Image 2>&1
            $pushOut2 | ForEach-Object { Write-Host ("    " + $_) }
            if ($LASTEXITCODE -eq 0) {
                Write-Ok ("Pushed " + $Image)
                return
            }
            $joined = ($pushOut2 | Out-String)
        }
        throw ("docker push failed for " + $Image + "`nDocker output:`n" + $joined)
    }
    Write-Ok ("Pushed " + $Image)
}

function Deploy-OrUpdateContainerApp {
    param(
        [string]$Name,
        [string]$Rg,
        [string]$EnvName,
        [string]$Image,
        [string]$RegistryServer,
        [string]$RegistryUser,
        [string]$RegistryPass,
        [int]$TargetPort,
        [string[]]$EnvVars,
        [string]$Cpu,
        [string]$Memory,
        [int]$MinRep,
        [int]$MaxRep
    )

    $exists = Test-ContainerAppExists -Name $Name -Rg $Rg
    if (-not $exists) {
        Write-Ok ("Creating container app: " + $Name)
        az containerapp create `
            --name $Name `
            --resource-group $Rg `
            --environment $EnvName `
            --image $Image `
            --registry-server $RegistryServer `
            --registry-username $RegistryUser `
            --registry-password $RegistryPass `
            --target-port $TargetPort `
            --ingress external `
            --cpu $Cpu `
            --memory $Memory `
            --min-replicas $MinRep `
            --max-replicas $MaxRep `
            --env-vars $EnvVars | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw ("az containerapp create failed for " + $Name)
        }
    }
    else {
        Write-Ok ("Updating container app: " + $Name)
        # Ensure registry credentials remain configured
        az containerapp registry set `
            --name $Name `
            --resource-group $Rg `
            --server $RegistryServer `
            --username $RegistryUser `
            --password $RegistryPass | Out-Null

        az containerapp update `
            --name $Name `
            --resource-group $Rg `
            --image $Image `
            --cpu $Cpu `
            --memory $Memory `
            --min-replicas $MinRep `
            --max-replicas $MaxRep `
            --set-env-vars $EnvVars | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw ("az containerapp update failed for " + $Name)
        }
    }
}

function Build-EnvVarArray {
    param([hashtable]$Pairs)
    $list = New-Object System.Collections.Generic.List[string]
    foreach ($k in $Pairs.Keys) {
        $v = $Pairs[$k]
        if ($null -eq $v) { $v = "" }
        # Quote-safe for az: KEY=VALUE
        $list.Add(("{0}={1}" -f $k, $v)) | Out-Null
    }
    return ,$list.ToArray()
}

# -----------------------------------------------------------------------------
# Pre-flight
# -----------------------------------------------------------------------------
Write-Step "Pre-flight checks"
Assert-Command "az"
Assert-Command "docker"
Assert-Command "curl.exe"

$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop (Linux containers) and retry."
}
Write-Ok "Docker is running"

$dotenv = Import-DotEnv -Path $EnvFile
Write-Ok ("Loaded env from " + $EnvFile)

$ANTHROPIC_API_KEY = Get-EnvOrDefault -Map $dotenv -Key "ANTHROPIC_API_KEY"
$VOYAGE_API_KEY = Get-EnvOrDefault -Map $dotenv -Key "VOYAGE_API_KEY"
$OPENAI_API_KEY = Get-EnvOrDefault -Map $dotenv -Key "OPENAI_API_KEY"
$GEMINI_API_KEY = Get-EnvOrDefault -Map $dotenv -Key "GEMINI_API_KEY"
$QDRANT_URL = Get-EnvOrDefault -Map $dotenv -Key "QDRANT_URL" -Default "http://localhost:6333"
$QDRANT_API_KEY = Get-EnvOrDefault -Map $dotenv -Key "QDRANT_API_KEY"
$EMBEDDING_PROVIDER = Get-EnvOrDefault -Map $dotenv -Key "EMBEDDING_PROVIDER" -Default "voyage"
$EMBEDDING_MODEL_NAME = Get-EnvOrDefault -Map $dotenv -Key "EMBEDDING_MODEL_NAME" -Default "voyage-4-lite"
$EMBEDDING_DIMENSIONS = Get-EnvOrDefault -Map $dotenv -Key "EMBEDDING_DIMENSIONS"
$LLM_PROVIDER = Get-EnvOrDefault -Map $dotenv -Key "LLM_PROVIDER" -Default "anthropic"
$LLM_MODEL_NAME = Get-EnvOrDefault -Map $dotenv -Key "LLM_MODEL_NAME" -Default "anthropic/claude-3-5-haiku-20241022"
$LLM_REASONING_MODEL = Get-EnvOrDefault -Map $dotenv -Key "LLM_REASONING_MODEL" -Default "anthropic/claude-3-5-sonnet-20240620"
$QDRANT_IN_MEMORY = Get-EnvOrDefault -Map $dotenv -Key "QDRANT_IN_MEMORY" -Default "false"
$QDRANT_TIMEOUT = Get-EnvOrDefault -Map $dotenv -Key "QDRANT_TIMEOUT" -Default "120"

if ($LLM_PROVIDER -eq "anthropic" -and -not $ANTHROPIC_API_KEY) {
    if ($OPENAI_API_KEY) {
        Write-WarnLine "ANTHROPIC_API_KEY missing; backend will fall back to OpenAI if LLM_PROVIDER stays anthropic."
    }
    elseif ($GEMINI_API_KEY) {
        Write-WarnLine "ANTHROPIC_API_KEY missing; backend will fall back to Gemini if LLM_PROVIDER stays anthropic."
    }
    else {
        throw "ANTHROPIC_API_KEY is empty in .env (required when LLM_PROVIDER=anthropic, or set OPENAI/GEMINI for fallback)"
    }
}
if ($LLM_PROVIDER -eq "openai" -and -not $OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is empty in .env (required when LLM_PROVIDER=openai)"
}
if ($LLM_PROVIDER -eq "gemini" -and -not $GEMINI_API_KEY) {
    throw "GEMINI_API_KEY is empty in .env (required when LLM_PROVIDER=gemini)"
}
if ($EMBEDDING_PROVIDER -eq "voyage" -and -not $VOYAGE_API_KEY) {
    if ($OPENAI_API_KEY) {
        Write-WarnLine "VOYAGE_API_KEY missing; set it for voyage-4-lite or switch EMBEDDING_PROVIDER=openai"
    }
    else {
        throw "VOYAGE_API_KEY is empty in .env (required when EMBEDDING_PROVIDER=voyage). Get a key at https://dash.voyageai.com/ (not Anthropic Claude key)."
    }
}
if ($EMBEDDING_PROVIDER -eq "openai" -and -not $OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is empty in .env (required when EMBEDDING_PROVIDER=openai)"
}
if ($EMBEDDING_PROVIDER -eq "gemini" -and -not $GEMINI_API_KEY) {
    throw "GEMINI_API_KEY is empty in .env (required when EMBEDDING_PROVIDER=gemini)"
}

if (-not $SkipLogin) {
    Write-Step "Azure login / subscription"
    $acctProbe = Invoke-AzQuiet -AzArgs @("account", "show", "-o", "json")
    $accountJson = $acctProbe.Output
    if (-not $accountJson -or $acctProbe.ExitCode -ne 0) {
        az login | Out-Null
        $accountJson = az account show -o json
    }
    if ($SubscriptionId) {
        az account set --subscription $SubscriptionId | Out-Null
        $accountJson = az account show -o json
    }
    $account = $accountJson | ConvertFrom-Json
    Write-Ok ("Subscription: " + $account.name + " (" + $account.id + ")")
}

Write-Step "Register resource providers"
Ensure-Provider -Namespace "Microsoft.App"
Ensure-Provider -Namespace "Microsoft.ContainerRegistry"
Ensure-Provider -Namespace "Microsoft.OperationalInsights"

Write-Step "Ensure resource group"
az group create --name $ResourceGroup --location $Location | Out-Null
Write-Ok ("Resource group: " + $ResourceGroup + " (" + $Location + ")")

Write-Step "Ensure Azure Container Registry (no ACR Tasks)"
$ACR = Ensure-Acr -Rg $ResourceGroup -Loc $Location -PreferredName $AcrName
$acrCreds = Get-AcrCredentials -RegistryName $ACR
$ACR_SERVER = $acrCreds.Server
Write-Ok ("Registry server: " + $ACR_SERVER)
Write-Ok ("ACR admin user: " + $acrCreds.Username)

Write-Step "Docker login to ACR"
Connect-AcrDocker -RegistryName $ACR -AcrCreds $acrCreds

Write-Step "Ensure Container Apps environment"
Ensure-ContainerAppEnvironment -Name $EnvironmentName -Rg $ResourceGroup -Loc $Location

$backendEnvMap = @{
    ANTHROPIC_API_KEY    = $ANTHROPIC_API_KEY
    VOYAGE_API_KEY       = $VOYAGE_API_KEY
    OPENAI_API_KEY       = $OPENAI_API_KEY
    GEMINI_API_KEY       = $GEMINI_API_KEY
    QDRANT_URL           = $QDRANT_URL
    QDRANT_API_KEY       = $QDRANT_API_KEY
    QDRANT_IN_MEMORY     = $QDRANT_IN_MEMORY
    QDRANT_TIMEOUT       = $QDRANT_TIMEOUT
    EMBEDDING_PROVIDER   = $EMBEDDING_PROVIDER
    EMBEDDING_MODEL_NAME = $EMBEDDING_MODEL_NAME
    LLM_PROVIDER         = $LLM_PROVIDER
    LLM_MODEL_NAME       = $LLM_MODEL_NAME
    LLM_REASONING_MODEL  = $LLM_REASONING_MODEL
    CORS_ORIGINS         = "http://localhost:3000,http://127.0.0.1:3000"
}
if ($EMBEDDING_DIMENSIONS) {
    $backendEnvMap["EMBEDDING_DIMENSIONS"] = $EMBEDDING_DIMENSIONS
}

$deployBackend = -not $FrontendOnly
$deployFrontend = -not $BackendOnly
$BACKEND_URL = $null
$FRONTEND_URL = $null
$BACKEND_IMAGE = $ACR_SERVER + "/release-assurance-api:latest"
$FRONTEND_IMAGE = $ACR_SERVER + "/release-assurance-web:latest"
$scaleMin = $MinReplicas
$scaleMax = $MaxReplicas
if ($SkipScale) {
    $scaleMin = 1
    $scaleMax = $MaxReplicas
}

if ($deployBackend) {
    Write-Step "Build + push backend image (local Docker, no ACR Tasks)"
    Invoke-DockerBuildPush `
        -Image $BACKEND_IMAGE `
        -Dockerfile (Join-Path $RepoRoot "backend\Dockerfile") `
        -Context $RepoRoot `
        -RegistryName $ACR `
        -AcrCreds $acrCreds

    Write-Step ("Deploy backend Container App (" + $BackendName + ")")
    $backendEnvVars = Build-EnvVarArray -Pairs $backendEnvMap
    Deploy-OrUpdateContainerApp `
        -Name $BackendName `
        -Rg $ResourceGroup `
        -EnvName $EnvironmentName `
        -Image $BACKEND_IMAGE `
        -RegistryServer $ACR_SERVER `
        -RegistryUser $acrCreds.Username `
        -RegistryPass $acrCreds.Password `
        -TargetPort 8000 `
        -EnvVars $backendEnvVars `
        -Cpu $BackendCpu `
        -Memory $BackendMemory `
        -MinRep $scaleMin `
        -MaxRep $scaleMax

    $BACKEND_URL = Get-ContainerAppUrl -Name $BackendName -Rg $ResourceGroup
    Write-Ok ("Backend URL: " + $BACKEND_URL)

    Write-Step "Health check backend"
    Start-Sleep -Seconds 8
    try {
        $health = curl.exe -sS --max-time 30 ($BACKEND_URL + "/api/v1/health")
        Write-Ok ("{0}" -f $health)
    }
    catch {
        Write-WarnLine "Health check not ready yet (cold start). URL is still valid."
    }
}
else {
    Write-Step "Skip backend deploy (FrontendOnly) - resolve existing URL"
    if (-not (Test-ContainerAppExists -Name $BackendName -Rg $ResourceGroup)) {
        throw ("Backend app " + $BackendName + " does not exist. Run full deploy or -BackendOnly first.")
    }
    $BACKEND_URL = Get-ContainerAppUrl -Name $BackendName -Rg $ResourceGroup
    Write-Ok ("Backend URL: " + $BACKEND_URL)
}

if ($deployFrontend) {
    Write-Step ("Build + push frontend image (NEXT_PUBLIC_API_URL=" + $BACKEND_URL + ")")
    Invoke-DockerBuildPush `
        -Image $FRONTEND_IMAGE `
        -Dockerfile (Join-Path $RepoRoot "frontend\Dockerfile") `
        -Context (Join-Path $RepoRoot "frontend") `
        -BuildArgs @{ NEXT_PUBLIC_API_URL = $BACKEND_URL } `
        -RegistryName $ACR `
        -AcrCreds $acrCreds

    Write-Step ("Deploy frontend Container App (" + $FrontendName + ")")
    $feEnv = @("NEXT_PUBLIC_API_URL=" + $BACKEND_URL)
    Deploy-OrUpdateContainerApp `
        -Name $FrontendName `
        -Rg $ResourceGroup `
        -EnvName $EnvironmentName `
        -Image $FRONTEND_IMAGE `
        -RegistryServer $ACR_SERVER `
        -RegistryUser $acrCreds.Username `
        -RegistryPass $acrCreds.Password `
        -TargetPort 3000 `
        -EnvVars $feEnv `
        -Cpu $FrontendCpu `
        -Memory $FrontendMemory `
        -MinRep $scaleMin `
        -MaxRep $scaleMax

    $FRONTEND_URL = Get-ContainerAppUrl -Name $FrontendName -Rg $ResourceGroup
    Write-Ok ("Frontend URL: " + $FRONTEND_URL)

    if (Test-ContainerAppExists -Name $BackendName -Rg $ResourceGroup) {
        Write-Step "Patch backend CORS for frontend origin"
        $cors = "http://localhost:3000,http://127.0.0.1:3000," + $FRONTEND_URL
        az containerapp update `
            --name $BackendName `
            --resource-group $ResourceGroup `
            --set-env-vars ("CORS_ORIGINS=" + $cors) | Out-Null
        Write-Ok ("CORS_ORIGINS=" + $cors)
    }
}

if (-not $BACKEND_URL) {
    if (Test-ContainerAppExists -Name $BackendName -Rg $ResourceGroup) {
        try { $BACKEND_URL = Get-ContainerAppUrl -Name $BackendName -Rg $ResourceGroup } catch { $BACKEND_URL = "" }
    }
    else {
        $BACKEND_URL = ""
    }
}
if (-not $FRONTEND_URL -and -not $BackendOnly) {
    if (Test-ContainerAppExists -Name $FrontendName -Rg $ResourceGroup) {
        try { $FRONTEND_URL = Get-ContainerAppUrl -Name $FrontendName -Rg $ResourceGroup } catch { $FRONTEND_URL = "" }
    }
    else {
        $FRONTEND_URL = ""
    }
}

$summaryLines = @(
    "# Release Assurance - Azure deploy output"
    ("DeployedAt: " + (Get-Date -Format o))
    ("ResourceGroup: " + $ResourceGroup)
    ("Location: " + $Location)
    ("Environment: " + $EnvironmentName)
    ("ACR: " + $ACR_SERVER)
    ""
    ("BackendName: " + $BackendName)
    ("BackendImage: " + $BACKEND_IMAGE)
    ("BackendUrl: " + $BACKEND_URL)
    ("BackendHealth: " + $BACKEND_URL + "/api/v1/health")
    ("BackendDocs: " + $BACKEND_URL + "/docs")
    ""
    ("FrontendName: " + $FrontendName)
    ("FrontendImage: " + $FRONTEND_IMAGE)
    ("FrontendUrl: " + $FRONTEND_URL)
    ""
    ("LLM_PROVIDER: " + $LLM_PROVIDER)
    ("LLM_MODEL_NAME: " + $LLM_MODEL_NAME)
    ("LLM_REASONING_MODEL: " + $LLM_REASONING_MODEL)
    ("EMBEDDING_PROVIDER: " + $EMBEDDING_PROVIDER)
    ("EMBEDDING_MODEL_NAME: " + $EMBEDDING_MODEL_NAME)
    ""
    "Notes:"
    "- Build path uses local Docker + docker push (avoids ACR Tasks block)."
    "- Scale min-replicas=" + $scaleMin + " max-replicas=" + $scaleMax
)
$summary = ($summaryLines -join [Environment]::NewLine)
$outPath = Join-Path $RepoRoot "deploy-output.txt"
Set-Content -Path $outPath -Value $summary -Encoding UTF8

Write-Step "DEPLOYMENT COMPLETE"
Write-Host $summary -ForegroundColor Green
Write-Ok ("Wrote " + $outPath)
Write-Host ""
Write-Host ("Open UI:  " + $FRONTEND_URL) -ForegroundColor Magenta
Write-Host ("Open API: " + $BACKEND_URL + "/docs") -ForegroundColor Magenta
