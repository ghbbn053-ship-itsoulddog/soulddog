param(
  [string]$Config = "docs/github-intake/repos.txt",
  [string]$OutDir = "vendor",
  [switch]$Clone
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $Config)) {
  throw "Config not found: $Config"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path "docs/github-intake" | Out-Null

$rows = @()
$repos = Get-Content $Config | Where-Object { $_ -and -not $_.Trim().StartsWith("#") }

foreach ($repo in $repos) {
  $repo = $repo.Trim()
  if ($repo -notmatch "^[^/]+/[^/]+$") {
    Write-Host "Skip invalid repo: $repo"
    continue
  }

  $api = "https://api.github.com/repos/$repo"
  try {
    $meta = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "campus-ai-intake" }
  } catch {
    $rows += [pscustomobject]@{
      repo = $repo
      stars = -1
      updated_at = ""
      language = ""
      license = ""
      clone_path = ""
      status = "api_error"
      notes = $_.Exception.Message
    }
    continue
  }

  $clonePath = Join-Path $OutDir ($repo -replace "/", "__")
  if ($Clone) {
    if (!(Test-Path $clonePath)) {
      try {
        git clone --depth 1 ("https://github.com/" + $repo + ".git") $clonePath | Out-Null
      } catch {
        $rows += [pscustomobject]@{
          repo = $repo
          stars = $meta.stargazers_count
          updated_at = $meta.updated_at
          language = $meta.language
          license = ($meta.license.spdx_id)
          clone_path = $clonePath
          status = "clone_error"
          notes = $_.Exception.Message
        }
        continue
      }
    }
  }

  $readme = ""
  $readmeCandidates = @("README.md", "readme.md", "README.MD")
  foreach ($r in $readmeCandidates) {
    $p = Join-Path $clonePath $r
    if (Test-Path $p) {
      $readme = Get-Content $p -TotalCount 80 | Out-String
      break
    }
  }

  $fit = @()
  if ($readme -match "agent|multi-agent|workflow|orchestr") { $fit += "agent_orchestration" }
  if ($readme -match "tool|mcp|function calling") { $fit += "tooling" }
  if ($readme -match "stream|sse|realtime") { $fit += "streaming" }
  if ($readme -match "memory|state|graph") { $fit += "stateful_runtime" }
  if ($fit.Count -eq 0) { $fit += "general" }

  $rows += [pscustomobject]@{
    repo = $repo
    stars = $meta.stargazers_count
    updated_at = $meta.updated_at
    language = $meta.language
    license = ($meta.license.spdx_id)
    clone_path = $clonePath
    status = "ok"
    notes = ($fit -join ",")
  }
}

$jsonPath = "docs/github-intake/analysis.json"
$mdPath = "docs/github-intake/analysis.md"

$rows | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $jsonPath

$sorted = $rows | Sort-Object stars -Descending
$lines = @()
$lines += "# GitHub Intake Analysis"
$lines += ""
$lines += "| Repo | Stars | Updated | Lang | License | Fit | Status |"
$lines += "|---|---:|---|---|---|---|---|"
foreach ($r in $sorted) {
  $lines += "| $($r.repo) | $($r.stars) | $($r.updated_at) | $($r.language) | $($r.license) | $($r.notes) | $($r.status) |"
}
$lines -join "`n" | Set-Content -Encoding UTF8 $mdPath

Write-Host "Saved:"
Write-Host " - $jsonPath"
Write-Host " - $mdPath"
