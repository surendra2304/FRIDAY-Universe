param (
    [string]$AgentName = "all",
    [switch]$Force = $true
)

$agentMap = [ordered]@{
    "FRIDAY"    = "https://github.com/surendra2304/FRIDAY.git"
    "Inference" = "https://github.com/surendra2304/Inference.git"
    "Memora"    = "https://github.com/surendra2304/Memora.git"
    "Stratex"   = "https://github.com/surendra2304/Stratex.git"
    "IntelX"    = "https://github.com/surendra2304/IntelX.git"
    "Futuris"   = "https://github.com/surendra2304/Futuris.git"
    "Forge"     = "https://github.com/surendra2304/Forge.git"
    "VyralX"    = "https://github.com/surendra2304/VyralX.git"
    "Sentinel"  = "https://github.com/surendra2304/Sentinel.git"
    "Cortex"    = "https://github.com/surendra2304/Cortex.git"
}

function Sync-Agent {
    param([string]$Agent, [string]$RepoUrl)
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Syncing agent: $Agent -> $RepoUrl" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    
    $tempBranch = "temp-split-$($Agent.ToLower())"
    git branch -D $tempBranch 2>$null | Out-Null
    
    Write-Host "Running git subtree split for $Agent..." -ForegroundColor Yellow
    git subtree split --prefix=$Agent -b $tempBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to split subtree for $Agent"
        return
    }
    
    Write-Host "Pushing $tempBranch to $RepoUrl main..." -ForegroundColor Green
    if ($Force) {
        git push $RepoUrl "$($tempBranch):main" --force
    } else {
        git push $RepoUrl "$($tempBranch):main"
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Successfully synced $Agent to $RepoUrl" -ForegroundColor Green
    } else {
        Write-Error "Failed to push $Agent to $RepoUrl"
    }
    
    git branch -D $tempBranch 2>$null | Out-Null
}

if ($AgentName -eq "all") {
    foreach ($k in $agentMap.Keys) {
        Sync-Agent -Agent $k -RepoUrl $agentMap[$k]
    }
} elseif ($agentMap.Contains($AgentName)) {
    Sync-Agent -Agent $AgentName -RepoUrl $agentMap[$AgentName]
} else {
    $keys = ($agentMap.Keys -join ', ')
    Write-Error "Unknown agent: $AgentName. Available: ($keys)"
}
