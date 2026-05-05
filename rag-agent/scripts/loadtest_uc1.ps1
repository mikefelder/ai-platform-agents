# =============================================================================
# UC1 #4 - Concurrent users load test (PowerShell 5.1, ASCII only)
#
# Goal: prove no performance degradation with N concurrent users hammering
# the UC1 RAG endpoint via APIM. Reports per-request latency, p50/p95/p99,
# error count, and throughput.
#
# Usage (jumpbox):
#   $env:APIM_BASE = "https://ai-alz-apim-i40e.azure-api.net"
#   $env:APIM_SUBSCRIPTION_KEY = "<from KV>"
#   .\loadtest_uc1.ps1                # defaults: 5 users x 10 reqs each
#   .\loadtest_uc1.ps1 -Users 10 -RequestsPerUser 20
#
# Implementation note: PS5.1 has no proper async HTTP; we use background
# jobs (Start-Job) per user. Each job runs a tight loop hitting the endpoint
# and emitting one JSON line per request. Aggregation is done in the parent.
# =============================================================================

[CmdletBinding()]
param(
    [int]    $Users           = 5,
    [int]    $RequestsPerUser = 10,
    [string] $ApimBase        = $(if ($env:APIM_BASE) { $env:APIM_BASE } else { "https://ai-alz-apim-i40e.azure-api.net" }),
    [string] $ApimKey         = $env:APIM_SUBSCRIPTION_KEY,
    [string] $Model           = "gpt-4.1-mini",
    [string] $Prompt          = "What are the valve specifications for Project Alpha?"
)

$ErrorActionPreference = "Stop"

if (-not $ApimKey) {
    Write-Host "ERROR: APIM_SUBSCRIPTION_KEY env var not set." -ForegroundColor Red
    Write-Host "Fetch with (master sub, MSDN tenant):"
    Write-Host "  az rest --method post --uri 'https://management.azure.com/subscriptions/1784740a-1cf6-416b-b3db-bda6985970aa/resourceGroups/ai-lz-rg-msdn-mb44x/providers/Microsoft.ApiManagement/service/ai-alz-apim-i40e/subscriptions/master/listSecrets?api-version=2022-08-01' --query primaryKey -o tsv"
    exit 2
}

function H1($t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }

H1 ("UC1 #4 load test: " + $Users + " users x " + $RequestsPerUser + " requests = " + ($Users * $RequestsPerUser) + " total")
Write-Host ("Endpoint: " + $ApimBase + "/uc1/responses")
Write-Host ("Model:    " + $Model)

$jobScript = {
    param($userId, $count, $url, $key, $model, $prompt)

    $hdrs = @{
        "Ocp-Apim-Subscription-Key" = $key
        "Content-Type"              = "application/json"
    }
    $body = @{
        model = $model
        input = @(@{ role = "user"; content = $prompt })
    } | ConvertTo-Json -Depth 5

    $results = @()
    for ($i = 0; $i -lt $count; $i++) {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $status = 0
        $err = ""
        try {
            $r = Invoke-WebRequest -Uri $url -Method POST -Headers $hdrs -Body $body -TimeoutSec 60 -UseBasicParsing
            $status = [int]$r.StatusCode
        } catch {
            if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
            $err = $_.Exception.Message.Split("`n")[0]
        }
        $sw.Stop()
        $results += [PSCustomObject]@{
            user      = $userId
            seq       = $i
            status    = $status
            latencyMs = [int]$sw.Elapsed.TotalMilliseconds
            error     = $err
        }
    }
    return $results
}

$url = $ApimBase + "/uc1/responses"
$jobs = @()
$wallStart = Get-Date
for ($u = 1; $u -le $Users; $u++) {
    $jobs += Start-Job -ScriptBlock $jobScript -ArgumentList $u, $RequestsPerUser, $url, $ApimKey, $Model, $Prompt
}

Write-Host ("Spawned " + $jobs.Count + " worker jobs. Waiting...")
$null = $jobs | Wait-Job
$all = @()
foreach ($j in $jobs) {
    $all += Receive-Job -Job $j
    Remove-Job -Job $j
}
$wallEnd = Get-Date
$wallSec = ($wallEnd - $wallStart).TotalSeconds

# --- Aggregate ---
$total      = $all.Count
$ok         = ($all | Where-Object { $_.status -ge 200 -and $_.status -lt 300 }).Count
$rateLimit  = ($all | Where-Object { $_.status -eq 429 }).Count
$errors     = ($all | Where-Object { $_.status -ge 500 -or $_.status -eq 0 }).Count
$throttled  = ($all | Where-Object { $_.status -eq 401 -or $_.status -eq 403 }).Count

$lat = $all | Where-Object { $_.status -ge 200 -and $_.status -lt 300 } | ForEach-Object { $_.latencyMs } | Sort-Object
function Pct($sorted, $p) {
    if (-not $sorted -or $sorted.Count -eq 0) { return 0 }
    $idx = [int][math]::Ceiling(($p / 100.0) * $sorted.Count) - 1
    if ($idx -lt 0) { $idx = 0 }
    if ($idx -ge $sorted.Count) { $idx = $sorted.Count - 1 }
    return $sorted[$idx]
}
$p50 = Pct $lat 50
$p95 = Pct $lat 95
$p99 = Pct $lat 99
$avg = 0
if ($lat.Count -gt 0) { $avg = [int](($lat | Measure-Object -Average).Average) }
$rps = 0
if ($wallSec -gt 0) { $rps = [math]::Round($total / $wallSec, 2) }

H1 "Results"
Write-Host ("Wall clock         : " + [math]::Round($wallSec, 2) + " s")
Write-Host ("Total requests     : " + $total)
Write-Host ("  2xx success      : " + $ok)
Write-Host ("  429 rate-limited : " + $rateLimit)
Write-Host ("  401/403          : " + $throttled)
Write-Host ("  5xx / network    : " + $errors)
Write-Host ("Throughput         : " + $rps + " req/s")
Write-Host ("Latency (2xx only) :")
Write-Host ("  avg : " + $avg + " ms")
Write-Host ("  p50 : " + $p50 + " ms")
Write-Host ("  p95 : " + $p95 + " ms")
Write-Host ("  p99 : " + $p99 + " ms")

# Pass criteria for UC1 #4: zero 5xx, p95 within 2x single-user baseline.
# Caller can compare $p95 to a known baseline collected with -Users 1.
if ($errors -gt 0) {
    Write-Host "FAIL: 5xx/network errors observed under concurrency." -ForegroundColor Red
    exit 1
}
if ($ok -eq 0) {
    Write-Host "FAIL: zero successful requests." -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "PASS: no 5xx errors. Compare p95 to single-user baseline to confirm no degradation." -ForegroundColor Green

# Optional: dump raw per-request data for offline analysis
$out = Join-Path $PSScriptRoot ("loadtest_uc1_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".csv")
$all | Export-Csv -Path $out -NoTypeInformation
Write-Host ("Raw results written to: " + $out)
