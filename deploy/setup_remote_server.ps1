<#
.SYNOPSIS
    1-Click Automated Remote Server Deployer for FRIDAY Universe
.PARAMETER ServerIP
    The public IPv4 address of the Oracle Cloud Ubuntu instance.
.PARAMETER Domain
    Optional: DuckDNS or custom domain for automatic HTTPS.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP,

    [Parameter(Mandatory=$false)]
    [string]$Domain = ""
)

$ErrorActionPreference = "Stop"

$keyPath = "C:\Users\Surendra\.ssh\friday_universe_oracle.key"
$user = "ubuntu"
$remoteDir = "/opt/friday_universe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   🚀 1-CLICK ORACLE SERVER DEPLOYER - FRIDAY UNIVERSE    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Server Target: $user@$ServerIP" -ForegroundColor Yellow
Write-Host "SSH Key:       $keyPath" -ForegroundColor Yellow

# 1. Verify SSH Connection
Write-Host "`n[1/5] Testing SSH connectivity..." -ForegroundColor Cyan
try {
    $sshTest = ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $keyPath "$user@$ServerIP" "echo 'CONNECTED'"
    if ($sshTest -ne "CONNECTED") { throw "SSH handshake failed." }
    Write-Host "  -> SSH connection established successfully!" -ForegroundColor Green
} catch {
    Write-Error "Failed to connect via SSH to $ServerIP. Please check IP and ensure instance is RUNNING."
    exit 1
}

# 2. Upload Deployment Scripts
Write-Host "`n[2/5] Uploading deployment manifests and scripts..." -ForegroundColor Cyan
ssh -i $keyPath "$user@$ServerIP" "sudo mkdir -p $remoteDir && sudo chown -R ${user}:${user} $remoteDir"
scp -i $keyPath -r "$PSScriptRoot\bootstrap.sh" "$PSScriptRoot\docker-compose.yml" "$PSScriptRoot\Caddyfile" "$PSScriptRoot\start.sh" "$PSScriptRoot\stop.sh" "$PSScriptRoot\status.sh" "$user@${ServerIP}:$remoteDir/"
ssh -i $keyPath "$user@$ServerIP" "chmod +x $remoteDir/*.sh"
Write-Host "  -> Scripts uploaded and permissions set." -ForegroundColor Green

# 3. Configure Domain in Caddyfile if provided
if ($Domain -ne "") {
    Write-Host "`n[*] Configuring custom domain: $Domain" -ForegroundColor Cyan
    ssh -i $keyPath "$user@$ServerIP" "sed -i 's|{\$DOMAIN::80}|$Domain|g' $remoteDir/Caddyfile"
}

# 4. Execute Bootstrap on Remote Server
Write-Host "`n[3/5] Executing bootstrap on remote server (Installing Docker, 8GB Swap, Caddy, Firewall)..." -ForegroundColor Cyan
Write-Host "  -> This will take ~2-3 minutes. Please wait..." -ForegroundColor Gray
ssh -i $keyPath "$user@$ServerIP" "sudo bash $remoteDir/bootstrap.sh"

# 5. Copy Repositories & .env
Write-Host "`n[4/5] Syncing agent repositories and configuration to server..." -ForegroundColor Cyan
# Clone / sync repos directly on server for native ARM64 compilation
$repos = @("FRIDAY", "Cortex", "Forge", "Futuris", "Inference", "IntelX", "Memora", "Sentinel", "Stratex")
foreach ($repo in $repos) {
    Write-Host "  -> Syncing $repo..." -ForegroundColor Gray
    ssh -i $keyPath "$user@$ServerIP" "if [ ! -d '$remoteDir/$repo' ]; then git clone https://github.com/surendra2304/$repo.git $remoteDir/$repo; else cd $remoteDir/$repo && git pull; fi"
}

# Upload .env if exists
$localEnv = "D:\FRIDAY Universe\.env"
if (Test-Path $localEnv) {
    Write-Host "  -> Uploading environment configuration..." -ForegroundColor Gray
    scp -i $keyPath $localEnv "$user@${ServerIP}:$remoteDir/.env.production"
}

# 6. Launch All 9 Containers
Write-Host "`n[5/5] Launching all 9 microservices in Docker..." -ForegroundColor Cyan
ssh -i $keyPath "$user@$ServerIP" "bash $remoteDir/start.sh"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "   🎉 FRIDAY UNIVERSE DEPLOYMENT COMPLETE!               " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
if ($Domain -ne "") {
    Write-Host "Web Command Center: https://$Domain" -ForegroundColor Yellow
} else {
    Write-Host "Web Command Center: http://$ServerIP:10000" -ForegroundColor Yellow
}
