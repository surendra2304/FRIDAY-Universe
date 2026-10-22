param (
    [string]$AgentName = "all"
)

$agentMap = @{
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

if ($AgentName -eq "all") {
    foreach ($k in $agentMap.Keys) {
        Write-Host "Syncing $k to standalone repo..." -ForegroundColor Cyan
        git subtree push --prefix=$k $agentMap[$k] main
    }
} elseif ($agentMap.ContainsKey($AgentName)) {
    Write-Host "Syncing $AgentName to standalone repo..." -ForegroundColor Cyan
    git subtree push --prefix=$AgentName $agentMap[$AgentName] main
} else {
    $keys = ($agentMap.Keys -join ', ')
    Write-Error "Unknown agent: $AgentName. Available: ($keys)"
}
