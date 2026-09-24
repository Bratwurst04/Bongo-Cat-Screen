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
function Format-CallsPerSecond([double]$seconds) {
    if ($seconds -le 0) { return '0' }
    return ('{0:0.0}' -f (1 / $seconds))
}

function Parse-Decimal([string]$text) {
    # Swedish Windows commonly uses a comma while JSON uses a decimal point.
    # Accept either form, but never interpret the comma as a thousands separator.
    $normalised = $text.Trim().Replace(',', '.')
    return [double]::Parse(
        $normalised,
        [Globalization.NumberStyles]::Float,
        [Globalization.CultureInfo]::InvariantCulture
    )
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

$config = Read-JsonFile $ConfigPath
if ($null -eq $config) {
    [System.Windows.Forms.MessageBox]::Show('Kunde inte läsa Bongo Cats inställningar.', 'Bongo Cat') | Out-Null
    exit 1
}
if ($null -eq $config.spotify) { $config | Add-Member -NotePropertyName spotify -NotePropertyValue ([pscustomobject]@{}) }
if ($null -eq $config.startup) { $config | Add-Member -NotePropertyName startup -NotePropertyValue ([pscustomobject]@{}) }

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Bongo Cat - Inställningar'
$form.ClientSize = New-Object System.Drawing.Size(660, 520)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
Enable-DoubleBuffering $form

$title = New-Object System.Windows.Forms.Label
$title.Text = 'Spotify och BongoDesk'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 15, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(20, 16)
$title.AutoSize = $true
[void]$form.Controls.Add($title)

$toolTip = New-Object System.Windows.Forms.ToolTip
$toolTip.AutoPopDelay = 12000
$toolTip.InitialDelay = 350
$toolTip.ReshowDelay = 100

$apiInfo = New-Object System.Windows.Forms.Label
$apiInfo.Text = '?  Så fungerar uppdateringsintervallen'
$apiInfo.ForeColor = [System.Drawing.Color]::FromArgb(35, 100, 170)
$apiInfo.Location = New-Object System.Drawing.Point(24, 50)
$apiInfo.Size = New-Object System.Drawing.Size(270, 22)
[void]$form.Controls.Add($apiInfo)
$toolTip.SetToolTip($apiInfo, 'Intervallen används bara när BongoDesk behöver Spotify Web API. 1 sekund betyder högst 1 API-anrop per sekund; 0,5 sekunder betyder högst 2. Spotify kan tillfälligt välja långsammare takt efter en begränsning.')

$diagnosticsButton = New-Object System.Windows.Forms.Button
$diagnosticsButton.Text = 'API-diagnostik...'
$diagnosticsButton.Location = New-Object System.Drawing.Point(500, 46)
$diagnosticsButton.Size = New-Object System.Drawing.Size(140, 28)
[void]$form.Controls.Add($diagnosticsButton)
$toolTip.SetToolTip($diagnosticsButton, 'Visar API-gränser, senaste adaptiva ändring och ESP32:ns minne i ett separat fönster.')

$statusGroup = New-Object System.Windows.Forms.GroupBox
$statusGroup.Text = 'Live-status (uppdateras varje sekund)'
$statusGroup.Location = New-Object System.Drawing.Point(20, 76)
$statusGroup.Size = New-Object System.Drawing.Size(620, 142)
[void]$form.Controls.Add($statusGroup)

$status = New-Object System.Windows.Forms.Label
$status.Text = 'Väntar på BongoDesks status...'
$status.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$status.Location = New-Object System.Drawing.Point(14, 24)
$status.Size = New-Object System.Drawing.Size(592, 108)
[void]$statusGroup.Controls.Add($status)

function Add-Field([string]$label, [string]$help, [string]$value, [int]$top, [string]$suffix) {
    $caption = New-Object System.Windows.Forms.Label
    $caption.Text = $label
    $caption.Location = [System.Drawing.Point]::new(22, ([int]$top + 3))
    $caption.Size = New-Object System.Drawing.Size(185, 22)
    [void]$form.Controls.Add($caption)

    $input = New-Object System.Windows.Forms.TextBox
    $input.Text = $value
    $input.Location = New-Object System.Drawing.Point(215, $top)
    $input.Size = New-Object System.Drawing.Size(78, 25)
    [void]$form.Controls.Add($input)

    $unit = New-Object System.Windows.Forms.Label
    $unit.Text = $suffix
    $unit.Location = [System.Drawing.Point]::new(301, ([int]$top + 4))
    $unit.Size = New-Object System.Drawing.Size(55, 22)
    [void]$form.Controls.Add($unit)

    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = '?'
    $hint.Font = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
    $hint.ForeColor = [System.Drawing.Color]::FromArgb(35, 100, 170)
    $hint.Location = New-Object System.Drawing.Point(365, ([int]$top + 4))
    $hint.Size = New-Object System.Drawing.Size(18, 22)
    [void]$form.Controls.Add($hint)
    $toolTip.SetToolTip($caption, $help)
    $toolTip.SetToolTip($input, $help)
    $toolTip.SetToolTip($hint, $help)
    return $input
}

function Config-Value([string]$name, [string]$fallback) {
    $property = $config.spotify.PSObject.Properties[$name]
    if ($null -eq $property -or $null -eq $property.Value -or "$($property.Value)" -eq '') { return $fallback }
    return "$($property.Value)"
}

$initialBox = Add-Field 'Vanlig uppdatering' 'Startintervallet när en låt spelas. BongoDesk anpassar sedan takten försiktigt.' (Config-Value 'api_initial_interval_seconds' '3') 238 'sekunder'
$minimumBox = Add-Field 'Snabbast automatiskt' 'Den lägsta tillåtna väntetiden. Du kan skriva 0,5 eller 0.5 – båda betyder högst 2 API-anrop per sekund.' (Config-Value 'api_min_interval_seconds' '1') 278 'sekunder'
$idleBox = Add-Field 'Uppdatering vid paus' 'Väntetid när musik är pausad eller när inget spelas. Den ska vara minst lika lång som vanlig uppdatering.' (Config-Value 'api_idle_interval_seconds' '10') 318 'sekunder'
$retryBox = Add-Field 'Försök med albumomslag' 'Hur många gånger BongoDesk försöker hämta ett saknat omslag innan den fortsätter utan det.' (Config-Value 'artwork_retry_attempts' '5') 358 'gånger'
$script:savedFastest = Parse-Decimal $minimumBox.Text

$startup = New-Object System.Windows.Forms.CheckBox
$startup.Text = 'Starta BongoDesk när du loggar in i Windows'
$startup.Checked = [bool]$config.startup.start_with_windows
$startup.Location = New-Object System.Drawing.Point(22, 406)
$startup.AutoSize = $true
[void]$form.Controls.Add($startup)
$toolTip.SetToolTip($startup, 'Startar BongoDesk i bakgrunden när du loggar in i Windows.')

$resourceInfo = New-Object System.Windows.Forms.Label
$resourceInfo.Text = '?  Vad betyder CPU och RAM?'
$resourceInfo.Location = New-Object System.Drawing.Point(22, 432)
$resourceInfo.Size = New-Object System.Drawing.Size(220, 22)
$resourceInfo.ForeColor = [System.Drawing.Color]::FromArgb(35, 100, 170)
[void]$form.Controls.Add($resourceInfo)
$toolTip.SetToolTip($resourceInfo, 'Datorn totalt är hela datorns sammanlagda CPU- och RAM-användning. BongoDesk visas på samma 0–100-skala: dess andel av datorns totala CPU-kapacitet. I diagnostikens hjälptext kan du även se motsvarigheten per logisk CPU-kärna. ESP32-skärmen räknas inte in i någon av siffrorna.')

$message = New-Object System.Windows.Forms.Label
$message.Location = New-Object System.Drawing.Point(22, 470)
$message.Size = New-Object System.Drawing.Size(385, 28)
$message.ForeColor = [System.Drawing.Color]::FromArgb(35, 100, 170)
[void]$form.Controls.Add($message)

$save = New-Object System.Windows.Forms.Button
$save.Text = 'Spara ändringar'
$save.Location = New-Object System.Drawing.Point(482, 466)
$save.Size = New-Object System.Drawing.Size(158, 34)
[void]$form.Controls.Add($save)

$save.Add_Click({
    try {
        $initial = Parse-Decimal $initialBox.Text
        $minimum = Parse-Decimal $minimumBox.Text
        $idle = Parse-Decimal $idleBox.Text
        $retries = [int]::Parse($retryBox.Text)
        if ($minimum -lt 0.5 -or $initial -lt $minimum -or $idle -lt $initial -or $idle -gt 300 -or $retries -lt 1 -or $retries -gt 5) {
            throw 'Använd minst 0,5 s och välj snabbast ≤ vanlig ≤ paus. Omslagsförsök måste vara 1–5.'
        }
        $fresh = Read-JsonFile $ConfigPath
        if ($null -eq $fresh) { throw 'Kunde inte läsa inställningsfilen igen.' }
        if ($null -eq $fresh.spotify) { $fresh | Add-Member -NotePropertyName spotify -NotePropertyValue ([pscustomobject]@{}) }
        if ($null -eq $fresh.startup) { $fresh | Add-Member -NotePropertyName startup -NotePropertyValue ([pscustomobject]@{}) }
        $fresh.spotify | Add-Member api_initial_interval_seconds $initial -Force
        $fresh.spotify | Add-Member api_min_interval_seconds $minimum -Force
        $fresh.spotify | Add-Member api_idle_interval_seconds $idle -Force
        $fresh.spotify | Add-Member artwork_retry_attempts $retries -Force
        $fresh.startup | Add-Member start_with_windows ([bool]$startup.Checked) -Force
        $temporary = "$ConfigPath.tmp"
        [IO.File]::WriteAllText($temporary, ($fresh | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $ConfigPath -Force
        $script:savedFastest = $minimum
        $message.ForeColor = [System.Drawing.Color]::FromArgb(35, 100, 170)
        $message.Text = "Sparat. Snabbast automatiskt: $(Format-Seconds $minimum) s (högst $(Format-CallsPerSecond $minimum) API-anrop/s)."
    } catch {
        $message.ForeColor = [System.Drawing.Color]::Firebrick
        $message.Text = $_.Exception.Message
    }
})

function Format-Age([double]$seconds) {
    $seconds = [math]::Max(0, [math]::Round($seconds))
    if ($seconds -lt 60) { return "$seconds sek sedan" }
    if ($seconds -lt 3600) { return "$( [math]::Floor($seconds / 60) ) min sedan" }
    return "$( [math]::Floor($seconds / 3600) ) h sedan"
}

function Get-UnixTime { return [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }

function Get-DiagnosticsText($info) {
    if ($null -eq $info) { return 'Väntar på status från BongoDesk...' }

    $pacing = $info.media.spotify.pacing
    if ($null -eq $pacing) {
        $apiText = "Spotify API är inte aktivt just nu.\r\nIngen pacing- eller gränsdata finns att visa."
    } else {
        $limits = $pacing.rate_limits
        $change = $pacing.last_change
        $limitText = "Spotify-gränser (HTTP 429): 15 min: $($limits.last_15_minutes)  |  1 h: $($limits.last_hour)  |  24 h: $($limits.last_24_hours)"
        if ($null -ne $change) {
            $from = [double]$change.from_seconds
            $to = [double]$change.to_seconds
            $difference = $to - $from
            $direction = if ($difference -lt 0) { 'snabbare' } elseif ($difference -gt 0) { 'långsammare' } else { 'oförändrad' }
            $reason = switch ("$($change.reason)") {
                'spotify_rate_limit' { 'Spotify-gräns (429)' }
                'manual_reset' { 'manuell återställning' }
                default { 'lugn period utan gränsträffar' }
            }
            $changeText = "Senaste adaptiva ändring: $(Format-Seconds $from) s → $(Format-Seconds $to) s ($direction, $reason; $(Format-Age ((Get-UnixTime) - [double]$change.at)))."
        } else {
            $changeText = 'Adaptiv pacing har ännu inte ändrat intervallet under den här sessionen.'
        }
        $activity = if ([bool]$pacing.adjusting_now) { 'Anpassar aktivt just nu.' } else { 'Ingen adaptiv ändring pågår just nu.' }
        $apiText = "$limitText`r`n$activity $changeText"
    }

    $esp32 = $info.esp32
    if ($null -ne $esp32 -and $null -ne $esp32.free_heap_bytes) {
        $heap = [math]::Round(([double]$esp32.free_heap_bytes / 1KB), 1)
        $heapTotal = [math]::Round(([double]$esp32.heap_total_bytes / 1KB), 1)
        $minimumHeap = [math]::Round(([double]$esp32.min_heap_bytes / 1KB), 1)
        $psram = [math]::Round(([double]$esp32.free_psram_bytes / 1KB), 1)
        $psramTotal = [math]::Round(([double]$esp32.psram_total_bytes / 1KB), 1)
        $psramText = if ($psramTotal -gt 0) { "$psram KiB ledigt av $psramTotal KiB" } else { 'saknas på den här modulen' }
        $espText = "ESP32 live-minne: heap $heap KiB ledigt av $heapTotal KiB (lägsta sedan start: $minimumHeap KiB); PSRAM: $psramText. Senaste mätning: $(Format-Age ([double]$esp32.status_age_seconds))."
    } elseif ($null -ne $esp32 -and -not [bool]$esp32.connected) {
        $espText = 'ESP32: inte ansluten.'
    } else {
        $espText = 'ESP32: väntar på första minnesmätningen.'
    }
    return "$apiText`r`n`r`n$espText`r`nESP32 CPU: inte aktiverad. Diagnostikrapporten använder ungefär 0,14 % av seriell kapacitet och mycket mindre än 0,1 % CPU (en kort minnesavläsning var femte sekund). Full FreeRTOS-profilering skulle kräva ett annat runtime-bygge och ge osäker extra overhead."
}

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
        return [pscustomobject]@{ Alert='Väntar på status från BongoDesk...'; HasLimit=$false; Api='—'; Adaptive='—'; Change='—'; Heap='—'; Cpu='—'; Connection='—'; CpuEnabled=$false }
    }
    $pacing = $info.media.spotify.pacing
    $hasLimit = $false
    if ($null -ne $pacing) {
        $limits = $pacing.rate_limits
        $last15 = [int]$limits.last_15_minutes
        $lastHour = [int]$limits.last_hour
        $lastDay = [int]$limits.last_24_hours
        $hasLimit = ($last15 -gt 0 -or $lastHour -gt 0 -or $lastDay -gt 0)
        $api = "429-träffar: $last15 senaste 15 min  |  $lastHour senaste timmen  |  $lastDay senaste dygnet"
        $adaptive = if ([bool]$pacing.adjusting_now) { 'Anpassar takten aktivt nu' } else { 'Ingen ändring just nu' }
        $change = $pacing.last_change
        if ($null -ne $change) {
            $direction = if ([double]$change.to_seconds -gt [double]$change.from_seconds) { 'långsammare' } elseif ([double]$change.to_seconds -lt [double]$change.from_seconds) { 'snabbare' } else { 'oförändrad' }
            $reason = switch ("$($change.reason)") { 'spotify_rate_limit' { '429-gräns' }; 'manual_reset' { 'manuell återställning' }; default { 'lugn period' } }
            $changeText = "$(Format-Seconds ([double]$change.from_seconds)) s → $(Format-Seconds ([double]$change.to_seconds)) s ($direction, $reason; $(Format-Age ((Get-UnixTime) - [double]$change.at)))"
        } else { $changeText = 'Ingen adaptiv ändring under denna session.' }
    } else {
        $api = 'Spotify API används inte just nu.'; $adaptive = '—'; $changeText = '—'
    }
    $esp32 = $info.esp32
    if ($null -ne $esp32 -and $null -ne $esp32.free_heap_bytes) {
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
        $heapText = 'Väntar på ESP32.'; $cpuText = '—'; $connection = 'ESP32 är inte ansluten.'; $cpuEnabled = $false
    }
    $alert = if ($hasLimit) { 'Spotify API-gränsen har nåtts. BongoDesk bevakar eller har saktat ned takten.' } else { 'Ingen Spotify-gräns har nåtts i de sparade tidsfönstren.' }
    return [pscustomobject]@{ Alert=$alert; HasLimit=$hasLimit; Api=$api; Adaptive=$adaptive; Change=$changeText; Heap=$heapText; Cpu=$cpuText; Connection=$connection; CpuEnabled=$cpuEnabled }
}

function Add-DiagnosticRow($table, [int]$row, [string]$caption, [string]$help, $toolTip) {
    $rowTop = $row * 38
    $name = New-Object System.Windows.Forms.Label
    $name.Text = $caption; $name.TextAlign = 'MiddleLeft'; $name.AutoSize = $false
    $name.Location = New-Object System.Drawing.Point(0, $rowTop); $name.Size = New-Object System.Drawing.Size(190, 38)
    $name.Padding = New-Object System.Windows.Forms.Padding(9, 0, 4, 0)
    $name.BackColor = [System.Drawing.Color]::FromArgb(232, 240, 248)
    $name.ForeColor = [System.Drawing.Color]::FromArgb(25, 76, 119)
    $name.Font = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
    $name.BorderStyle = 'FixedSingle'
    $value = New-Object System.Windows.Forms.Label
    $value.Text = 'Väntar...'; $value.TextAlign = 'MiddleLeft'; $value.AutoSize = $false
    $value.Location = New-Object System.Drawing.Point(190, $rowTop); $value.Size = New-Object System.Drawing.Size(498, 38)
    $value.Padding = New-Object System.Windows.Forms.Padding(10, 0, 8, 0)
    $value.BackColor = [System.Drawing.Color]::White
    $value.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $value.BorderStyle = 'FixedSingle'
    [void]$table.Controls.Add($name); [void]$table.Controls.Add($value)
    $toolTip.SetToolTip($name, $help); $toolTip.SetToolTip($value, $help)
    return $value
}

function Show-ApiDiagnostics {
    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = 'Bongo Cat - API-diagnostik'
    $dialog.ClientSize = New-Object System.Drawing.Size(730, 430)
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.StartPosition = 'CenterParent'

    $heading = New-Object System.Windows.Forms.Label
    $heading.Text = 'Diagnostik: Spotify API och ESP32'
    $heading.Font = New-Object System.Drawing.Font('Segoe UI', 13, [System.Drawing.FontStyle]::Bold)
    $heading.Location = New-Object System.Drawing.Point(20, 16)
    $heading.AutoSize = $true
    [void]$dialog.Controls.Add($heading)

    $alertIcon = New-Object System.Windows.Forms.Label
    $alertIcon.Text = '!'; $alertIcon.TextAlign = 'MiddleCenter'
    $alertIcon.Font = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
    $alertIcon.ForeColor = [System.Drawing.Color]::White; $alertIcon.BackColor = [System.Drawing.Color]::Firebrick
    $alertIcon.Location = New-Object System.Drawing.Point(20, 54); $alertIcon.Size = New-Object System.Drawing.Size(28, 28)
    [void]$dialog.Controls.Add($alertIcon)

    $alert = New-Object System.Windows.Forms.Label
    $alert.Location = New-Object System.Drawing.Point(54, 54); $alert.Size = New-Object System.Drawing.Size(656, 28)
    $alert.TextAlign = 'MiddleLeft'; $alert.Padding = New-Object System.Windows.Forms.Padding(9, 0, 4, 0)
    $alert.Font = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
    [void]$dialog.Controls.Add($alert)

    $table = New-Object System.Windows.Forms.Panel
    $table.Location = New-Object System.Drawing.Point(20, 96); $table.Size = New-Object System.Drawing.Size(690, 232)
    $table.BorderStyle = 'FixedSingle'
    Enable-DoubleBuffering $table
    [void]$dialog.Controls.Add($table)
    $apiRow = Add-DiagnosticRow $table 0 'Spotify-gränser' 'Antal HTTP 429-svar. Det röda utropstecknet visas när en gräns har nåtts.' $toolTip
    $adaptiveRow = Add-DiagnosticRow $table 1 'Adaptiv takt' 'BongoDesk höjer väntetiden efter en gräns och sänker den stegvis när det är lugnt.' $toolTip
    $changeRow = Add-DiagnosticRow $table 2 'Senaste ändring' 'Exakt förändring av API-takten och varför den gjordes.' $toolTip
    $heapRow = Add-DiagnosticRow $table 3 'ESP32-minne' 'Heap är ESP32:ns arbetsminne. Lägsta värdet sedan start hjälper att upptäcka minnesläckor.' $toolTip
    $cpuRow = Add-DiagnosticRow $table 4 'ESP32 CPU' 'Valfri grov aktivitetsuppskattning från FreeRTOS-idleticks. Inte en exakt profilerare per uppgift.' $toolTip
    $connectionRow = Add-DiagnosticRow $table 5 'Anslutning' 'Tidpunkten för den senast mottagna statusraden från ESP32.' $toolTip

    $close = New-Object System.Windows.Forms.Button
    $close.Text = 'Stäng'
    $close.Location = New-Object System.Drawing.Point(590, 374)
    $close.Size = New-Object System.Drawing.Size(100, 32)
    $close.Add_Click({ $dialog.Close() })
    [void]$dialog.Controls.Add($close)

    $resetSafety = New-Object System.Windows.Forms.Button
    $resetSafety.Text = 'Använd vald snabbast-takt nu'
    $resetSafety.Location = New-Object System.Drawing.Point(310, 374)
    $resetSafety.Size = New-Object System.Drawing.Size(260, 32)
    $resetSafety.Add_Click({
        try {
            Request-PacingReset
            $dialog.Text = 'Bongo Cat - API-diagnostik (snabbast-takt begärd)'
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Kunde inte återställa säkerhetsgränsen: $($_.Exception.Message)", 'Bongo Cat') | Out-Null
        }
    })
    [void]$dialog.Controls.Add($resetSafety)

    $cpuToggle = New-Object System.Windows.Forms.Button
    $cpuToggle.Text = 'Aktivera CPU-mätning'
    $cpuToggle.Location = New-Object System.Drawing.Point(20, 374); $cpuToggle.Size = New-Object System.Drawing.Size(270, 32)
    $cpuToggle.Add_Click({
        try {
            $current = Read-JsonFile $StatusPath
            $enabled = if ($null -ne $current -and $null -ne $current.esp32) { [bool]$current.esp32.cpu_meter_enabled } else { $false }
            Set-CpuDiagnosticsEnabled (-not $enabled)
            $cpuToggle.Enabled = $false; $cpuToggle.Text = 'Skickar ändringen till ESP32...'
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Kunde inte ändra CPU-mätningen: $($_.Exception.Message)", 'Bongo Cat') | Out-Null
        }
    })
    [void]$dialog.Controls.Add($cpuToggle)

    $dialog.Tag = [pscustomobject]@{ Api=$apiRow; Adaptive=$adaptiveRow; Change=$changeRow; Heap=$heapRow; Cpu=$cpuRow; Connection=$connectionRow; Alert=$alert; AlertIcon=$alertIcon; CpuToggle=$cpuToggle }

    $diagnosticTimer = New-Object System.Windows.Forms.Timer
    $diagnosticTimer.Interval = 1000
    $diagnosticTimer.Add_Tick({
        $values = Get-DiagnosticValues (Read-JsonFile $StatusPath)
        $view = $dialog.Tag
        $table.SuspendLayout()
        Set-ControlTextIfChanged $view.Api $values.Api; Set-ControlTextIfChanged $view.Adaptive $values.Adaptive; Set-ControlTextIfChanged $view.Change $values.Change
        Set-ControlTextIfChanged $view.Heap $values.Heap; Set-ControlTextIfChanged $view.Cpu $values.Cpu; Set-ControlTextIfChanged $view.Connection $values.Connection
        Set-ControlTextIfChanged $view.Alert $values.Alert
        if ($view.AlertIcon.Visible -ne $values.HasLimit) { $view.AlertIcon.Visible = $values.HasLimit }
        $alertBack = if ($values.HasLimit) { [System.Drawing.Color]::MistyRose } else { [System.Drawing.Color]::Honeydew }
        $alertFore = if ($values.HasLimit) { [System.Drawing.Color]::Firebrick } else { [System.Drawing.Color]::FromArgb(38, 101, 57) }
        if ($view.Alert.BackColor -ne $alertBack) { $view.Alert.BackColor = $alertBack }
        if ($view.Alert.ForeColor -ne $alertFore) { $view.Alert.ForeColor = $alertFore }
        $cpuButtonText = if ($values.CpuEnabled) { 'Stäng av CPU-mätning' } else { 'Aktivera CPU-mätning' }
        Set-ControlTextIfChanged $view.CpuToggle $cpuButtonText
        $table.ResumeLayout($false)
        $view.CpuToggle.Enabled = $true
    })
    $diagnosticTimer.Start()
    $dialog.Add_FormClosed({ $diagnosticTimer.Stop(); $diagnosticTimer.Dispose() })
    [void]$dialog.ShowDialog($form)
}

$diagnosticsButton.Add_Click({ Show-ApiDiagnostics })

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1000
$timer.Add_Tick({
    $info = Read-JsonFile $StatusPath
    if ($null -eq $info) {
        $status.Text = 'Väntar på BongoDesks status...'
        return
    }
    $sourceText = switch ("$($info.media.current_source)") {
        'windows_spotify' { 'Windows Spotify-session (ingen återkommande Spotify API-pollning)' }
        'spotify_api' { 'Spotify Web API (intervallen nedan används)' }
        default { 'Ingen aktiv Spotify-källa just nu' }
    }
    $api = $info.media.spotify.pacing
    if ($null -ne $api) {
        $current = [double]$api.interval_seconds
        $floor = [double]$api.safe_interval_seconds
        $rate = [double]$api.calls_per_second
        $fastest = $script:savedFastest
        $apiText = "Källa: $sourceText`r`nMätt API-takt: $([math]::Round($rate, 1)) anrop/s de senaste 5 sekunderna. Nuvarande intervall: $(Format-Seconds $current) s.`r`nAdaptiv säkerhetsgräns: $(Format-Seconds $floor) s. Sparat snabbast-värde: $(Format-Seconds $fastest) s (högst $(Format-CallsPerSecond $fastest) anrop/s)."
        $limits = $api.rate_limits
        $hasApiLimit = ([int]$limits.last_15_minutes -gt 0 -or [int]$limits.last_hour -gt 0 -or [int]$limits.last_24_hours -gt 0)
    } else {
        $apiText = "Källa: $sourceText`r`nSpotify API är inte anslutet eller används inte just nu."
        $hasApiLimit = $false
    }
    $diagnosticsButton.Text = if ($hasApiLimit) { '! API-diagnostik...' } else { 'API-diagnostik...' }
    $diagnosticsButton.ForeColor = if ($hasApiLimit) { [System.Drawing.Color]::Firebrick } else { [System.Drawing.SystemColors]::ControlText }
    $memoryFree = [double]$info.system_memory_available_mib / 1024
    $memoryTotal = [double]$info.system_memory_total_mib / 1024
    $logicalCpus = [int]$info.logical_cpu_count
    if ($logicalCpus -lt 1) { $logicalCpus = 1 }
    $pcText = "Datorn totalt: $($info.system_cpu_percent)% CPU, RAM $([math]::Round($memoryFree, 1)) GiB ledigt av $([math]::Round($memoryTotal, 1)) GiB. BongoDesk: $($info.app_cpu_percent)% av datorns totala CPU-kapacitet ($($info.app_cpu_percent_one_core)% av en logisk kärna), $($info.app_memory_mib) MiB RAM."
    $esp32 = $info.esp32
    if ($null -ne $esp32 -and $null -ne $esp32.free_heap_bytes) {
        $freeHeap = [math]::Round(([double]$esp32.free_heap_bytes / 1KB), 1)
        $totalHeap = [math]::Round(([double]$esp32.heap_total_bytes / 1KB), 1)
        $espText = "ESP32: heap $freeHeap KiB ledigt av $totalHeap KiB."
    } else {
        $espText = 'ESP32: väntar på minnesmätning.'
    }
    Set-ControlTextIfChanged $status "$apiText`r`n$pcText`r`n$espText"
})
$timer.Start()
$form.Add_Shown({ $form.TopMost = $false })
[void]$form.ShowDialog()
