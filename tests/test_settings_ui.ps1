param([string]$PreviewDirectory = '')
$ErrorActionPreference = 'Stop'
$companionRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\companion'))
$testRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\build\ui-test'))
[void][IO.Directory]::CreateDirectory($testRoot)
$ConfigPath = Join-Path $testRoot 'fixture-config.json'
$StatusPath = Join-Path $testRoot 'fixture-status.json'
$config = Get-Content (Join-Path $companionRoot 'default_config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$config | Add-Member custom_unrelated 'preserve-me'
$config.spotify | Add-Member client_id 'fixture-id' -Force
$config.spotify | Add-Member api_initial_interval_seconds 3.5 -Force
$config.connection.baudrate = 230400
$config | ConvertTo-Json -Depth 8 | Set-Content $ConfigPath -Encoding UTF8
function Write-FixtureStatus($sample) { $sample | ConvertTo-Json -Depth 12 | Set-Content $StatusPath -Encoding UTF8 }
$sample = @'
{"system_cpu_percent":18,"system_ram_percent":61,"system_memory_available_mib":12698,"system_memory_total_mib":32768,"app_cpu_percent":0.3,"app_cpu_percent_one_core":4.8,"app_memory_mib":62,"logical_cpu_count":16,"esp32":{"connected":true,"free_heap_bytes":182324,"heap_total_bytes":320000,"min_heap_bytes":178536,"free_psram_bytes":0,"psram_total_bytes":0,"cpu_meter_enabled":false,"cpu_estimate_percent":null,"status_age_seconds":2},"media":{"current_source":"windows_spotify","api_only_idle":false,"effective_poll_interval_seconds":null,"spotify":{"state":"ready","pacing":{"rate_limits":{"total":3,"total_since":1728000000,"legacy_events_included":1,"last_15_minutes":0,"last_hour":0,"last_24_hours":0},"calls_last_15_minutes":8,"calls_last_30_seconds":1,"interval_seconds":3,"safe_interval_seconds":2,"quota_poll_floor_seconds":0,"adjusting_now":false,"last_change":null}}}}
'@ | ConvertFrom-Json
Write-FixtureStatus $sample
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$entryErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $companionRoot 'settings.ps1'),[ref]$null,[ref]$entryErrors)
if ($entryErrors) { throw "Entry parser errors: $entryErrors" }
$functions=$ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)
foreach ($function in $functions) { Invoke-Expression $function.Extent.Text }
$view=Get-Content (Join-Path $companionRoot 'settings-view.ps1') -Raw -Encoding UTF8
$viewErrors=$null
$null=[Management.Automation.Language.Parser]::ParseInput($view,[ref]$null,[ref]$viewErrors)
if ($viewErrors) { throw "View parser errors: $viewErrors" }
$view=$view.Replace('Join-Path $PSScriptRoot','Join-Path $companionRoot').Replace('$timer.Start()','').Replace('[void]$form.ShowDialog()','')
Invoke-Expression $view
# Show offscreen with zero opacity solely to create native handles and focus.
# No engine, real config, serial port, Spotify request or installed EXE is used.
$form.ShowInTaskbar=$false; $form.Opacity=0; $form.StartPosition='Manual'; $form.Location=[Drawing.Point]::new(-20000,-20000)
$form.Show(); [Windows.Forms.Application]::DoEvents()
$script:assertions=0
function Assert([bool]$condition,[string]$failure) {
    if (-not $condition) { throw $failure }
    $script:assertions++
}
function Render([string]$name,[string]$page,[int]$width=960,[int]$height=740,$scrollTo=$null) {
    Select-Page $page; $form.ClientSize=[Drawing.Size]::new($width,$height)
    $form.PerformLayout(); [Windows.Forms.Application]::DoEvents()
    if ($null -ne $scrollTo) { $viewport.ScrollControlIntoView($scrollTo); [Windows.Forms.Application]::DoEvents() }
    if ($PreviewDirectory) {
        [void][IO.Directory]::CreateDirectory($PreviewDirectory)
        $bitmap=[Drawing.Bitmap]::new($form.Width,$form.Height)
        $form.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$form.Width,$form.Height))
        $bitmap.Save((Join-Path $PreviewDirectory "$name.png")); $bitmap.Dispose()
    }
    Assert ($shell.Bottom -le $form.ClientSize.Height -and $main.Bottom -le $shell.ClientSize.Height) "Shell exceeds native window: $name"
    if ($footer.Visible) {
        Assert ($footer.Bottom -le $main.ClientSize.Height) "Footer clipped: $name"
        Assert ($actions.Height -ge $save.Height) "Save action clipped: $name"
        Assert ($save.Bottom -le $actions.ClientSize.Height -and $actions.Bottom -le ($footer.ClientSize.Height-$footer.Padding.Bottom)) "Actions overflow footer: $name"
        Assert ($footer.Height -le $message.Height+$message.Margin.Vertical+$actions.Height+$footer.Padding.Vertical+2) "Save row reserves excess empty space: $name"
    } else { Assert ($viewport.Bottom -ge $main.ClientSize.Height-1) "Hidden footer leaves empty space: $name" }
    Assert ($viewport.ClientSize.Width -gt 400) "Content width too small: $name"
    function Check-Labels($container) {
        foreach ($control in $container.Controls) {
            if ($control -is [Windows.Forms.Label] -and $control.Visible -and $control.Text) {
                $preferred=$control.GetPreferredSize([Drawing.Size]::new($control.Width,0))
                Assert ($control.Height -ge $preferred.Height) "Wrapped text clipped in ${name}: $($control.Text)"
            }
            if ($control.Visible -and $control.HasChildren) { Check-Labels $control }
        }
    }
    Check-Labels $form
}
try {
    Assert ($fieldSpecs.Count -eq 5) 'Expected the five existing numeric settings'
    Assert (-not (Test-Dirty)) 'Initial view is dirty'
    Assert (-not $save.Enabled) 'Initial save should be disabled'
    Assert ($connectionTitle.Text -eq 'Ansluten till skärmen') 'Fresh device status missing'
    Assert ($spotifyTitle.Text -eq 'Spotify på den här datorn') 'Local Spotify source missing'
    Assert (-not $footer.Visible) 'Save controls should be hidden on an unchanged Overview'
    Assert (-not $script:advancedExpanded) 'Advanced settings should start collapsed'
    Assert ($initialBox.Text -eq '3,5') 'Loaded decimal value not presented in Swedish'
    Render 'overview' 'Översikt'
    Render 'settings' 'Inställningar'
    Assert ($footer.Visible -and -not $advancedContent.Visible) 'Settings should show save controls and hide advanced fields'
    [void]$advancedToggle.Focus(); $advancedToggle.PerformClick()
    Assert ($advancedContent.Visible -and $advancedToggle.Text -like 'Dölj*') 'Expansion failed'
    Render 'settings-advanced' 'Inställningar' 960 740 $idleBox
    Render 'settings-artwork' 'Inställningar' 960 740 $retryBox
    $minimumBox.Text='0,5'; [void]$minimumBox.Focus(); Set-AdvancedExpanded $false
    Assert ($advancedToggle.Focused -and $minimumBox.Text -eq '0,5') 'Collapse lost values or focus'
    Select-Page 'Översikt'
    Assert ($footer.Visible -and (Test-Dirty)) 'Dirty settings were forgotten after changing page'
    Render 'overview-unsaved' 'Översikt'
    [void]$undo.Focus(); Undo-Settings
    Assert (-not $footer.Visible -and $navButtons['Översikt'].Focused) 'Focus was left in the hidden save area'
    Render 'diagnostics' 'Diagnostik'
    Assert (-not $footer.Visible) 'Unchanged Diagnostics should hide save controls'
    Render 'diagnostics-screen' 'Diagnostik' 960 740 $cpuToggle
    Render 'settings-minimum' 'Inställningar' 824 611
    Assert (-not $advancedContent.Visible) 'Navigation unexpectedly expanded advanced fields'
    $minimumBox.Text='0,5'; $connectBox.Text='20,5'; $startup.Checked=$false
    Assert (Test-Dirty) 'Editing did not mark dirty'
    Assert ($save.Enabled -and $undo.Enabled) 'Edit actions remain disabled'
    Assert (Save-Settings) "Valid Swedish decimals rejected: $($message.Text)"
    $fresh=Read-JsonFile $ConfigPath
    Assert ($fresh.spotify.api_min_interval_seconds -eq 0.5 -and $fresh.spotify.api_only_poll_interval_seconds -eq 20.5) 'Decimal values not saved'
    Assert ($fresh.custom_unrelated -eq 'preserve-me' -and $fresh.spotify.client_id -eq 'fixture-id' -and $fresh.connection.baudrate -eq 230400) 'Unrelated configuration changed'
    Assert (-not (Test-Dirty)) 'Saved form remains dirty'
    $before=[IO.File]::ReadAllText($ConfigPath)
    $connectBox.Text='2'
    Assert (-not (Save-Settings)) 'Out-of-range Connect value accepted'
    Assert ([IO.File]::ReadAllText($ConfigPath) -ceq $before) 'Invalid save changed the config'
    Assert ($currentPage -eq 'Inställningar' -and $errors.GetError($connectBox) -ne '') 'Invalid field is not identified'
    Assert ($form.ActiveControl -eq $connectBox -or $connectBox.Focused) 'Invalid field did not receive focus'
    Render 'validation-error' 'Inställningar' 960 740
    Undo-Settings
    Assert ($connectBox.Text -eq '20,5' -and -not (Test-Dirty)) 'Undo did not restore saved values'
    $initialBox.Text='40'; $idleBox.Text='50'
    Set-AdvancedExpanded $false; Select-Page 'Översikt'
    Assert (-not (Save-Settings)) 'Value above configured API max accepted'
    Assert ($advancedContent.Visible -and $initialBox.Focused -and $currentPage -eq 'Inställningar') 'Validation did not open and focus the hidden invalid field'
    Render 'validation-hidden-field' 'Inställningar' 960 740 $initialBox
    Undo-Settings
    Set-AdvancedExpanded $false
    $minimumBox.Text='NaN'
    Assert (-not (Save-Settings)) 'NaN accepted'
    Undo-Settings
    $retryBox.Text='1,5'
    Assert (-not (Save-Settings)) 'Fractional retry count accepted'
    Undo-Settings
    $connectBox.Text='25'
    function Request-SaveChoice { return [Windows.Forms.DialogResult]::Cancel }
    Assert (-not (Confirm-Close)) 'Cancel should leave the window open'
    function Request-SaveChoice { return [Windows.Forms.DialogResult]::No }
    Assert (Confirm-Close) 'Discard should allow closing'
    Assert ([IO.File]::ReadAllText($ConfigPath) -ceq $before) 'Discard wrote configuration'
    function Request-SaveChoice { return [Windows.Forms.DialogResult]::Yes }
    Assert (Confirm-Close) 'Save on close failed'
    Assert ((Read-JsonFile $ConfigPath).spotify.api_only_poll_interval_seconds -eq 25) 'Close-save did not persist'
    $connectBox.Text='0'
    Assert (-not (Confirm-Close)) 'Invalid save on close should leave the window open'
    Undo-Settings
    # External edits made while the UI is open must survive a subsequent save.
    $fresh=Read-JsonFile $ConfigPath; $fresh.custom_unrelated='changed-elsewhere'
    $fresh | ConvertTo-Json -Depth 8 | Set-Content $ConfigPath -Encoding UTF8
    $connectBox.Text='15'; Assert (Save-Settings) 'Save after external edit failed'
    Assert ((Read-JsonFile $ConfigPath).custom_unrelated -eq 'changed-elsewhere') 'External edit overwritten'
    $connectBox.Text='16'; Select-Page 'Diagnostik'; [void]$save.Focus(); $save.PerformClick()
    Assert (-not $footer.Visible -and $navButtons['Diagnostik'].Focused -and -not (Test-Dirty)) 'Saving from Diagnostics left focus in hidden controls'
    $sample.media.spotify.state='rate_limited'
    $sample.media.spotify | Add-Member retry_remaining_seconds 34696 -Force
    Write-FixtureStatus $sample; Update-LiveStatus
    Assert ($spotifyTitle.Text -eq 'Spotify på den här datorn' -and $spotifyNotice.Text -like '*Windows-sessionen används fortfarande*') 'Local Spotify wrongly replaced by API cooldown'
    Render 'local-with-cooldown' 'Översikt' 824 611
    $sample.media.current_source='spotify_api'; $sample.media.effective_poll_interval_seconds=60
    Write-FixtureStatus $sample; Update-LiveStatus
    Assert ($spotifyNotice.Visible -and $spotifyNotice.Text -like '*9 h 39 min*' -and $spotifyTitle.Text -eq 'Spotify Connect väntar') 'Cooldown wait missing'
    Render 'connect-waiting' 'Översikt' 960 740
    $sample.esp32.connected=$false
    Write-FixtureStatus $sample; Update-LiveStatus
    Assert ($connectionTitle.Text -eq 'Ingen kontakt med skärmen' -and -not $cpuToggle.Enabled) 'Disconnected UI incorrect'
    Assert ($diagnosticRows.Heap.Text -like '*Ingen aktuell*') 'Old ESP32 memory shown as current'
    Assert ($diagnosticRows.Connection.Text -like '*inte ansluten*') 'Disconnected screen reported as connected'
    Render 'disconnected' 'Översikt'
    (Get-Item $StatusPath).LastWriteTimeUtc=[DateTime]::UtcNow.AddMinutes(-2)
    Update-LiveStatus
    Assert ($connectionTitle.Text -eq 'Status uppdateras inte' -and $pcSummary.Text -like '*ingen aktuell*') 'Stale status displayed as fresh'
    Render 'stale-status' 'Översikt'
    $sample.esp32.connected=$true; Write-FixtureStatus $sample; Update-LiveStatus
    Select-Page 'Diagnostik'
    function Request-PacingChoice { return [Windows.Forms.DialogResult]::Yes }
    $safetyReset.PerformClick()
    Assert ($resetMessage.Visible -and $resetMessage.Text -like '*begärd*' -and -not $footer.Visible) 'Immediate action feedback disappeared with save controls'
    Assert ((Read-JsonFile $ConfigPath).spotify.api_reset_safety_requested_at -gt 0) 'Pacing reset request missing'
    Render 'diagnostics-action' 'Diagnostik' 960 740 $resetMessage
    Select-Page 'Diagnostik'; $cpuToggle.PerformClick()
    Assert ((Read-JsonFile $ConfigPath).diagnostics.esp32_cpu_meter_enabled -and -not $cpuToggle.Enabled) 'CPU toggle did not save and wait for acknowledgement'
    $sample.esp32.cpu_meter_enabled=$true; Write-FixtureStatus $sample; Update-LiveStatus
    Assert ($cpuToggle.Enabled -and $cpuMessage.Text -like '*bekräftat*') 'CPU acknowledgement missing'
    Select-Page 'Inställningar'
    [void]$startup.Focus(); [void]$form.SelectNextControl($startup,$true,$true,$true,$true)
    Assert ($connectBox.Focused) 'Keyboard order does not reach Connect after startup'
    $sample.media.spotify.pacing | Add-Member last_change ([pscustomobject]@{ from_seconds=0.5; to_seconds=120; reason='spotify_rate_limit'; at=((Get-UnixTime)-120) }) -Force
    $sample.esp32 | Add-Member psram_total_bytes 8388608 -Force; $sample.esp32 | Add-Member free_psram_bytes 7234567 -Force
    Write-FixtureStatus $sample; Update-LiveStatus
    Render 'diagnostics-long' 'Diagnostik' 824 611
    Render 'diagnostics-long-screen' 'Diagnostik' 824 611 $cpuMessage
    Set-AdvancedExpanded $false
    # Layout stress, not a claim of a real Windows monitor/DPI test.
    $form.AutoScaleMode='None'
    function Get-FontSizes($control) {
        [pscustomobject]@{ Control=$control; Size=$control.Font.Size; Style=$control.Font.Style }
        foreach ($child in $control.Controls) { Get-FontSizes $child }
    }
    $fontSizes=@(Get-FontSizes $form)
    $form.Scale([Drawing.SizeF]::new(1.5,1.5))
    foreach ($item in $fontSizes) { $item.Control.Font=[Drawing.Font]::new('Segoe UI',($item.Size*1.5),$item.Style) }
    Render 'overview-scale150' 'Översikt' 1440 1000
    Render 'settings-scale150' 'Inställningar' 1440 1000
    Set-AdvancedExpanded $true
    Render 'settings-advanced-scale150' 'Inställningar' 1440 1000 $initialBox
    Write-Output "Settings UI: $script:assertions assertions passed; isolated native renders complete."
} finally {
    $script:savedEdits=Get-EditSnapshot
    $form.Close(); $form.Dispose()
}
