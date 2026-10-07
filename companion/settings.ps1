param(
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$StatusPath
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json) }
    catch { return $null }
}

function Format-Seconds([double]$seconds) { return ('{0:0.0}' -f $seconds) }

function Format-429-Baseline($limits) {
    if ($null -eq $limits -or [double]$limits.total_since -le 0) { return 'äldre historik kan saknas' }
    $since = [DateTimeOffset]::FromUnixTimeSeconds([long][math]::Floor([double]$limits.total_since)).ToLocalTime().ToString('yyyy-MM-dd')
    $legacy = [int]$limits.legacy_events_included
    return "från $since, +$legacy äldre; äldre kan saknas"
}

function Parse-Decimal([string]$text) {
    # Swedish Windows commonly uses a comma while JSON uses a decimal point.
    # Accept either form, but never interpret the comma as a thousands separator.
    $normalised = $text.Trim().Replace(',', '.')
    $number = [double]::Parse(
        $normalised,
        [Globalization.NumberStyles]::Float,
        [Globalization.CultureInfo]::InvariantCulture
    )
    if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) { throw 'Ange ett ändligt tal.' }
    return $number
}

function Enable-DoubleBuffering($control) {
    # WinForms otherwise repaints the full dialog for each live label update.
    $property = [System.Windows.Forms.Control].GetProperty(
        'DoubleBuffered',
        [System.Reflection.BindingFlags]'Instance,NonPublic'
    )
    if ($null -ne $property) { $property.SetValue($control, $true, $null) }
}

function Set-ControlTextIfChanged($control, [string]$text) {
    if ($control.Text -cne $text) { $control.Text = $text }
}

function Config-Value([string]$name, [string]$fallback) {
    $property = $config.spotify.PSObject.Properties[$name]
    if ($null -eq $property -or $null -eq $property.Value -or "$($property.Value)" -eq '') { return $fallback }
    return "$($property.Value)"
}

function Format-Age([double]$seconds) {
    $seconds = [math]::Max(0, [math]::Round($seconds))
    if ($seconds -lt 60) { return "$seconds sek sedan" }
    if ($seconds -lt 3600) { return "$( [math]::Floor($seconds / 60) ) min sedan" }
    return "$( [math]::Floor($seconds / 3600) ) h sedan"
}

function Get-UnixTime { return [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }

function Request-PacingReset {
    $fresh = Read-JsonFile $ConfigPath
    if ($null -eq $fresh) { throw 'Kunde inte läsa inställningsfilen igen.' }
    if ($null -eq $fresh.spotify) { $fresh | Add-Member -NotePropertyName spotify -NotePropertyValue ([pscustomobject]@{}) }
    $fresh.spotify | Add-Member api_reset_safety_requested_at (Get-UnixTime) -Force
    $temporary = "$ConfigPath.tmp"
    [IO.File]::WriteAllText($temporary, ($fresh | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $ConfigPath -Force
}

function Set-CpuDiagnosticsEnabled([bool]$enabled) {
    $fresh = Read-JsonFile $ConfigPath
    if ($null -eq $fresh) { throw 'Kunde inte läsa inställningsfilen igen.' }
    if ($null -eq $fresh.diagnostics) { $fresh | Add-Member -NotePropertyName diagnostics -NotePropertyValue ([pscustomobject]@{}) }
    $fresh.diagnostics | Add-Member esp32_cpu_meter_enabled $enabled -Force
    $temporary = "$ConfigPath.tmp"
    [IO.File]::WriteAllText($temporary, ($fresh | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $ConfigPath -Force
}

function Get-DiagnosticValues($info) {
    if ($null -eq $info) {
        return [pscustomobject]@{ Alert='Väntar på status från BongoDesk...'; HasLimit=$false; Api='—'; Windows='—'; Adaptive='—'; Change='—'; Calls='—'; Heap='—'; Cpu='—'; Connection='—'; CpuEnabled=$false }
    }
    $pacing = $info.media.spotify.pacing
    $hasLimit = $false
    if ($null -ne $pacing) {
        $limits = $pacing.rate_limits
        $last15 = [int]$limits.last_15_minutes
        $lastHour = [int]$limits.last_hour
        $lastDay = [int]$limits.last_24_hours
        $hasLimit = ($last15 -gt 0 -or $lastHour -gt 0 -or $lastDay -gt 0 -or
                     "$($info.media.spotify.state)" -eq 'rate_limited')
        $api = "Totalt $($limits.total) ($(Format-429-Baseline $limits))"
        $windows = "15 min: $last15  |  1 h: $lastHour  |  24 h: $lastDay"
        $effective = $info.media.effective_poll_interval_seconds
        $adaptive = if ($null -ne $effective) { "Connect: minst $(Format-Seconds ([double]$effective)) s; adaptiv $(Format-Seconds ([double]$pacing.interval_seconds)) s; säker $(Format-Seconds ([double]$pacing.safe_interval_seconds)) s" } else { "API-gräns: $(Format-Seconds ([double]$pacing.interval_seconds)) s; lokal Windows-källa behöver ingen Connect-poll" }
        $callsText = "$($pacing.calls_last_15_minutes) senaste 15 min, $($pacing.calls_last_30_seconds) senaste 30 s (denna körning)"
        $change = $pacing.last_change
        if ($null -ne $change) {
            $direction = if ([double]$change.to_seconds -gt [double]$change.from_seconds) { 'långsammare' } elseif ([double]$change.to_seconds -lt [double]$change.from_seconds) { 'snabbare' } else { 'oförändrad' }
            $reason = switch ("$($change.reason)") { 'spotify_rate_limit' { '429-gräns' }; 'manual_reset' { 'manuell återställning' }; default { 'lugn period' } }
            $changeText = "$(Format-Seconds ([double]$change.from_seconds)) s → $(Format-Seconds ([double]$change.to_seconds)) s ($direction, $reason; $(Format-Age ((Get-UnixTime) - [double]$change.at)))"
        } else { $changeText = 'Ingen adaptiv ändring under denna session.' }
    } else {
        $api = 'Spotify API används inte just nu.'; $windows = '—'; $adaptive = '—'; $changeText = '—'; $callsText = '—'
    }
    $esp32 = $info.esp32
    if ([bool]$esp32.connected -and $null -ne $esp32.free_heap_bytes) {
        $heap = [math]::Round(([double]$esp32.free_heap_bytes / 1KB), 1)
        $heapTotal = [math]::Round(([double]$esp32.heap_total_bytes / 1KB), 1)
        $minimumHeap = [math]::Round(([double]$esp32.min_heap_bytes / 1KB), 1)
        $heapText = "$heap KiB ledigt av $heapTotal KiB totalt (lägsta: $minimumHeap KiB)"
        if ([double]$esp32.psram_total_bytes -gt 0) { $heapText += "; PSRAM: $([math]::Round(([double]$esp32.free_psram_bytes / 1KB), 1)) KiB ledigt av $([math]::Round(([double]$esp32.psram_total_bytes / 1KB), 1)) KiB" }
        $cpuEnabled = [bool]$esp32.cpu_meter_enabled
        if ($cpuEnabled -and $null -ne $esp32.cpu_estimate_percent) { $cpuText = "$($esp32.cpu_estimate_percent) % aktivitet (grov uppskattning över $([math]::Round(([double]$esp32.cpu_sample_ms / 1000), 1)) sek)" }
        elseif ($cpuEnabled) { $cpuText = 'Startar mätning – första värdet kommer inom fem sekunder.' }
        else { $cpuText = 'Av – ingen extra CPU-mätning körs.' }
        $connection = "Ansluten. Senaste mätning: $(Format-Age ([double]$esp32.status_age_seconds))."
    } else {
        $heapText = 'Väntar på en aktuell minnesmätning.'; $cpuText = '—'; $cpuEnabled = [bool]$esp32.cpu_meter_enabled
        $connection = if ([bool]$esp32.connected) { 'Porten är öppen. Väntar på skärmens första status.' } else { 'Skärmen är inte ansluten.' }
    }
    $alert = if ("$($info.media.spotify.state)" -eq 'rate_limited') { "Spotify väntar på sin API-gräns. Tid kvar: cirka $($info.media.spotify.retry_remaining_seconds) s." }
             elseif ($hasLimit) { 'Spotify har nått API-gränsen under det senaste dygnet. Takten anpassas automatiskt.' }
             elseif ($null -eq $pacing) { 'Ingen aktuell API-gränsdata. Spotify API används inte just nu.' }
             else { 'Ingen Spotify-gräns har nåtts i de sparade tidsfönstren.' }
    return [pscustomobject]@{ Alert=$alert; HasLimit=$hasLimit; Api=$api; Windows=$windows; Adaptive=$adaptive; Change=$changeText; Calls=$callsText; Heap=$heapText; Cpu=$cpuText; Connection=$connection; CpuEnabled=$cpuEnabled }
}

$config = Read-JsonFile $ConfigPath
if ($null -eq $config) {
    [System.Windows.Forms.MessageBox]::Show('Kunde inte läsa Bongo Cats inställningar.', 'Bongo Cat') | Out-Null
    exit 1
}
if ($null -eq $config.spotify) { $config | Add-Member -NotePropertyName spotify -NotePropertyValue ([pscustomobject]@{}) }
if ($null -eq $config.startup) { $config | Add-Member -NotePropertyName startup -NotePropertyValue ([pscustomobject]@{}) }

. (Join-Path $PSScriptRoot 'settings-view.ps1')
