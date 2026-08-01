param(
    [switch]$ListCompatibilityExceptions
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BoundaryCheck = Join-Path $PSScriptRoot "check-public-release.ps1"

$candidate = @(& $BoundaryCheck -ListFiles)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to construct the public release candidate."
}

$migrationPrefix = "services/agent-api/app/db/migrations/versions/"
$pathPattern = '(?i)(^|[/_.-])(phase\d*|p\d+(?:[-_]?b\d+)?|wb\d*|r\d+(?:[-_]?b\d+)?|v[2-9]|canary|mock|stub|legacy|smoke)(?=[/_.-]|$)'
$contentPattern = '(?i)(\bphase(?:\s*[0-9]+)?\b|\bWB(?:\s*[0-9]+)?\b|\b(?:P|R)[0-9]+(?:[-_]?B[0-9]+)?\b|canary|\bmock\b|mock_|_mock|\bstub(?:bed|s)?\b|\blegacy\b|legacy[_-])'
$textExtensions = @(
    ".css", ".example", ".js", ".json", ".md", ".mjs", ".ps1",
    ".py", ".ts", ".tsx", ".yaml", ".yml"
)

# These are persisted database, historical event, or backward-read identifiers.
# They are intentionally narrow: ordinary product copy, API names, symbols, and
# file paths do not receive compatibility exemptions.
$compatibilityRules = @(
    @{ Path = "apps/web/next.config.ts"; Pattern = 'PHASE_DEVELOPMENT_SERVER|nextConfig\(phase' },
    @{ Path = "apps/web/features/conversation/ConversationWorkspace.tsx"; Pattern = 'startsWith\("mock"\)|mode === "mock"' },
    @{ Path = "services/agent-api/app/agents/nodes/growth_candidate_node.py"; Pattern = '"core-growth-r5-v1"' },
    @{ Path = "services/agent-api/app/agents/nodes/realtime_session_start_node.py"; Pattern = '"core-r13-v1"' },
    @{ Path = "services/agent-api/app/agents/nodes/realtime_speaker_turn_node.py"; Pattern = '"core_r13"' },
    @{ Path = "services/agent-api/app/agents/nodes/realtime_trace_logging_node.py"; Pattern = '"core-r13-v1"' },
    @{ Path = "services/agent-api/app/agents/nodes/user_state_snapshot_node.py"; Pattern = '"core-r8-user-state-ewma-v1"' },
    @{ Path = "services/agent-api/app/agents/prompts/conversation_prompt.py"; Pattern = '"Current phase".*current_phase' },
    @{ Path = "services/agent-api/app/core/algorithm_contract.py"; Pattern = '"core-r1-v1"' },
    @{ Path = "services/agent-api/app/db/models/bad_case.py"; Pattern = '"candidate_for_phase3"|"phase3_evidence_links"' },
    @{ Path = "services/agent-api/app/db/models/memory.py"; Pattern = '"legacy_private"' },
    @{ Path = "services/agent-api/app/memory/learned_reranker.py"; Pattern = '"core-r9-pairwise-logistic-v1"' },
    @{ Path = "services/agent-api/app/memory/retrieval.py"; Pattern = '"legacy_private"' },
    @{ Path = "services/agent-api/app/presence/contextual_bandit.py"; Pattern = '"core-r10-contextual-presence-shadow-v1"' },
    @{ Path = "services/agent-api/app/services/channel_simulation_service.py"; Pattern = '"mock_channel"' },
    @{ Path = "services/agent-api/app/db/models/channel_gateway_readiness.py"; Pattern = '"mock_projection"' },
    @{ Path = "services/agent-api/app/services/companion_channel_identity_service.py"; Pattern = '"mock_projection"' },
    @{ Path = "services/agent-api/app/services/companion_memory_service.py"; Pattern = '"legacy_private"' },
    @{ Path = "services/agent-api/app/services/companion_roster_service.py"; Pattern = 'COMPANION_PROVENANCE.*"legacy".*"smoke"' },
    @{ Path = "services/agent-api/app/services/companion_workspace_service.py"; Pattern = '"legacy_private"' },
    @{ Path = "services/agent-api/app/services/conversation_evidence_service.py"; Pattern = 'get\("is_mock"\)' },
    @{ Path = "services/agent-api/app/services/chronicle_summary_service.py"; Pattern = 'concise Chinese phase summary' },
    @{ Path = "services/agent-api/app/services/co_presence_service.py"; Pattern = '"core-r12-copresence-utility-v1"' },
    @{ Path = "services/agent-api/app/services/companion_growth_service.py"; Pattern = '"core_algorithm_r5"' },
    @{ Path = "services/agent-api/app/services/evaluation_service.py"; Pattern = '"Core Algorithm Completion R14"|"p0"|p0_safety_case' },
    @{ Path = "services/agent-api/app/services/memory_graph_service.py"; Pattern = '"legacy_private"' },
    @{ Path = "services/agent-api/app/services/memory_graph_service.py"; Pattern = '"core-r11-memory-graph-v1"' },
    @{ Path = "services/agent-api/app/services/memory_selection_policy_service.py"; Pattern = '"memory_reranker_canary(_history)?"' },
    @{ Path = "services/agent-api/app/services/memory_service.py"; Pattern = '"legacy_private"' },
    @{ Path = "services/agent-api/app/services/mutual_presence_service.py"; Pattern = '"phase4_(type|surface)"' },
    @{ Path = "services/agent-api/app/services/presence_service.py"; Pattern = '"phase4_(type|surface)"' },
    @{ Path = "services/agent-api/app/services/presence_timing_policy_service.py"; Pattern = '"presence_bandit_canary(_history)?"' },
    @{ Path = "services/agent-api/app/services/regression_service.py"; Pattern = '"core-r14-v1"|"p0"|p0_safety_case' },
    @{ Path = "services/agent-api/app/services/realtime_algorithm_service.py"; Pattern = '"core-r13-v1"' },
    @{ Path = "services/agent-api/app/services/strategy_service.py"; Pattern = '"phase4_(type|surface)"' },
    @{ Path = "services/agent-api/app/services/strategy_service.py"; Pattern = '"core-r7-strategy-v1"' },
    @{ Path = "services/agent-api/app/services/trace_service.py"; Pattern = 'metadata\.get\("phase(4_reoriented|5_realtime)"\)' }
)

function Test-CompatibilityLine {
    param(
        [string]$RelativePath,
        [string]$Line
    )
    foreach ($rule in $compatibilityRules) {
        if ($RelativePath -eq $rule.Path -and $Line -match $rule.Pattern) {
            return $true
        }
    }
    return $false
}

$pathViolations = @(
    $candidate |
        Where-Object { -not $_.StartsWith($migrationPrefix) } |
        Where-Object { $_ -match $pathPattern }
)

$contentViolations = [System.Collections.Generic.List[string]]::new()
$compatibilityHits = [System.Collections.Generic.List[string]]::new()

foreach ($relativePath in $candidate) {
    if (
        $relativePath.StartsWith($migrationPrefix) -or
        $relativePath -eq "apps/web/package-lock.json" -or
        $relativePath -eq "scripts/check-public-language.ps1"
    ) {
        continue
    }
    $extension = [IO.Path]::GetExtension($relativePath).ToLowerInvariant()
    if ($extension -notin $textExtensions) {
        continue
    }
    $absolutePath = Join-Path $ProjectRoot $relativePath
    foreach ($match in @(Select-String -LiteralPath $absolutePath -Pattern $contentPattern -AllMatches -Encoding utf8)) {
        if (Test-CompatibilityLine -RelativePath $relativePath -Line $match.Line) {
            $compatibilityHits.Add("$relativePath`:$($match.LineNumber)")
        } else {
            $contentViolations.Add("$relativePath`:$($match.LineNumber)")
        }
    }
}

if ($pathViolations.Count -gt 0 -or $contentViolations.Count -gt 0) {
    $details = @()
    if ($pathViolations.Count -gt 0) {
        $details += "Internal development language remains in public paths:"
        $details += $pathViolations
    }
    if ($contentViolations.Count -gt 0) {
        $details += "Internal development language remains in public content:"
        $details += $contentViolations
    }
    throw ($details -join [Environment]::NewLine)
}

if ($ListCompatibilityExceptions) {
    $compatibilityHits | Sort-Object -Unique
}

Write-Host (
    "[Echora] Public language gate passed: {0} files checked; {1} narrow compatibility references retained; migration revisions exempt." -f
    $candidate.Count,
    (@($compatibilityHits | Sort-Object -Unique)).Count
) -ForegroundColor Green
