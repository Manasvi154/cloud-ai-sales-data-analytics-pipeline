[CmdletBinding()]
param(
    [string]$TemplatePath = "infra/stepfunctions/analytics_orchestrator_full.asl.json",
    [string]$ValuesPath = "infra/config/full_stack_values.json",
    [string]$OutputPath = "infra/stepfunctions/analytics_orchestrator_full.rendered.asl.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $TemplatePath)) {
    throw "Template file not found: $TemplatePath"
}
if (-not (Test-Path $ValuesPath)) {
    throw "Values file not found: $ValuesPath"
}

$template = Get-Content -Path $TemplatePath -Raw
$values = Get-Content -Path $ValuesPath -Raw | ConvertFrom-Json -AsHashtable

foreach ($entry in $values.GetEnumerator()) {
    $key = [string]$entry.Key
    $value = [string]$entry.Value
    $template = $template.Replace($key, $value)
}

Set-Content -Path $OutputPath -Value $template
Write-Host "Rendered Step Functions definition written to $OutputPath" -ForegroundColor Green
