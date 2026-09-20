param(
    [Parameter(Mandatory = $true)]
    [string]$Model,

    [string]$BaseUrl = "http://localhost:11434/v1",

    [string]$OutputDir = "artifacts/citation_function_eval/openweight_provisional",

    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$env:OPENWEIGHT_BASE_URL = $BaseUrl
$env:OPENWEIGHT_MODEL = $Model
$env:OPENWEIGHT_API_KEY = "local"

Write-Host "Modelo open-weight: $Model"
Write-Host "Endpoint: $BaseUrl"
Write-Host "Conjunto: annotations/citation_function/provisional_test_gold.jsonl"
Write-Host "Salida: $OutputDir"

$argsList = @(
    "run",
    "python",
    "-m",
    "src.evaluation.commercial.orchestrate",
    "--mode",
    "openweight",
    "--gold",
    "annotations/citation_function/provisional_test_gold.jsonl",
    "--output-dir",
    $OutputDir
)

if ($CheckOnly) {
    $argsList += "--check-only"
}
else {
    $argsList += "--allow-provisional"
}

& uv @argsList

if ($LASTEXITCODE -ne 0) {
    throw "La evaluación terminó con código $LASTEXITCODE."
}

if ($CheckOnly) {
    Write-Host "Preflight completado. No se realizaron llamadas al modelo."
}
else {
    Write-Host ""
    Write-Host "Corrida provisional terminada."
    Write-Host "Revisar:"
    Write-Host "  $OutputDir/results.jsonl"
    Write-Host "  $OutputDir/summary.csv"
    Write-Host "  $OutputDir/run_metadata.json"
    Write-Host "  $OutputDir/metrics/evaluation_summary.csv"
    Write-Host ""
    Write-Host "IMPORTANTE: estos resultados son preliminares y no corresponden a un Test Gold definitivo."
}
