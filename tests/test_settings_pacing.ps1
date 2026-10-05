$source = Join-Path $PSScriptRoot '..\companion\settings.ps1'
$errorsFound = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path $source), [ref]$null, [ref]$errorsFound
)
if ($errorsFound) { throw "settings.ps1 parser errors: $errorsFound" }

$names = @('Format-Seconds', 'Format-429-Baseline', 'Format-Age',
           'Get-UnixTime', 'Get-DiagnosticValues')
$functions = $ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst]
}, $true)
foreach ($name in $names) {
    $definition = $functions | Where-Object { $_.Name -eq $name } | Select-Object -First 1
    if ($null -eq $definition) { throw "Missing function: $name" }
    Invoke-Expression $definition.Extent.Text
}

$sample = @'
{"media":{"spotify":{"pacing":{"rate_limits":{"total":3,"total_since":1728000000,"legacy_events_included":1,"last_15_minutes":0,"last_hour":0,"last_24_hours":0},"calls_last_15_minutes":8,"calls_last_30_seconds":1,"interval_seconds":3,"safe_interval_seconds":2,"adjusting_now":false}},"effective_poll_interval_seconds":15},"esp32":{"connected":false}}
'@ | ConvertFrom-Json
$values = Get-DiagnosticValues $sample
if ($values.Api -notlike '*Totalt 3*') { throw "Total 429 missing: $($values.Api)" }
if ($values.Api -notlike '*kan saknas*') { throw "Legacy caveat missing: $($values.Api)" }
if ($values.Windows -notlike '*15 min: 0*24 h: 0*') { throw "429 windows missing: $($values.Windows)" }
if ($values.Calls -notlike '*8 senaste 15 min*') { throw "Call window missing: $($values.Calls)" }
if ($values.Adaptive -notmatch 'Connect: minst 15[,.]0 s') { throw "Effective poll missing: $($values.Adaptive)" }
$sample.media.spotify | Add-Member state 'rate_limited' -Force
$limited = Get-DiagnosticValues $sample
if (-not $limited.HasLimit) { throw 'Active saved cooldown must show an alert' }
Write-Output 'Settings diagnostics formatting: OK'
