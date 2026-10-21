param([string]$PreviewDirectory = '')
$ErrorActionPreference = 'Stop'
$companionRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\companion'))
$testRoot = Join-Path ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\build\product-hardening-ui-tests'))) ([Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($testRoot)
$ConfigPath = Join-Path $testRoot 'fixture-config.json'
$StatusPath = Join-Path $testRoot 'fixture-status.json'
$config = Get-Content (Join-Path $companionRoot 'default_config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$config.connection.com_port = 'COM42'
$config.connection.baudrate = 921600
$config.connection | Add-Member custom_connection 'bevaras'
$config.spotify.client_id = 'synthetic-client-id'
$config.spotify | Add-Member unknown_budget ([pscustomobject]@{ counter=91; note='åäö' })
$config | Add-Member unrelated ([pscustomobject]@{ unicode='Återställ skärmen'; nested=@{ a=@{ b=@{ c=@{ d=@{ e=@{ f=@{ g=@{ h='deep-value' } } } } } } } } })
[IO.File]::WriteAllText($ConfigPath, ($config | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))

# Load definitions and the existing native view only. Substitute the port-name
# provider before creating the view: no real COM enumeration or device access.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $companionRoot 'settings.ps1'),[ref]$null,[ref]$parseErrors)
if ($parseErrors) { throw "Entry parser errors: $parseErrors" }
foreach ($definition in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
    Invoke-Expression $definition.Extent.Text
}
function Get-AvailableComPorts { return @('COM7', 'COM11') }
$view=Get-Content (Join-Path $companionRoot 'settings-view.ps1') -Raw -Encoding UTF8
$null=[Management.Automation.Language.Parser]::ParseInput($view,[ref]$null,[ref]$parseErrors)
if ($parseErrors) { throw "View parser errors: $parseErrors" }
$view=$view.Replace('Join-Path $PSScriptRoot','Join-Path $companionRoot').Replace('$timer.Start()','').Replace('[void]$form.ShowDialog()','')
Invoke-Expression $view
$form.ShowInTaskbar=$false; $form.Opacity=0; $form.StartPosition='Manual'; $form.Location=[Drawing.Point]::new(-20000,-20000)
$form.Show(); [Windows.Forms.Application]::DoEvents()
$script:assertions=0
function Assert([bool]$condition,[string]$failure) {
    if (-not $condition) { throw $failure }
    $script:assertions++
}
function Snapshot($value) { return ($value | ConvertTo-Json -Depth 100 -Compress) }
function Write-Fixture($value) { [IO.File]::WriteAllText($ConfigPath, ($value | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false)) }
function Render-Connection([string]$name,[int]$width=960,[int]$height=740) {
    Select-Page 'Inställningar'; $form.ClientSize=[Drawing.Size]::new($width,$height)
    $form.PerformLayout(); [Windows.Forms.Application]::DoEvents()
    $viewport.ScrollControlIntoView($restartNotice); [Windows.Forms.Application]::DoEvents()
    Assert ($portBox.Width -gt 100 -and $baudBox.Width -gt 100) "Connection controls clipped: $name"
    Assert ($restartNotice.Height -ge $restartNotice.GetPreferredSize([Drawing.Size]::new($restartNotice.Width,0)).Height) "Restart help clipped: $name"
    Assert ($footer.Bottom -le $main.ClientSize.Height) "Footer clipped: $name"
    if ($PreviewDirectory) {
        [void][IO.Directory]::CreateDirectory($PreviewDirectory)
        $bitmap=[Drawing.Bitmap]::new($form.Width,$form.Height)
        $form.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$form.Width,$form.Height))
        $bitmap.Save((Join-Path $PreviewDirectory "$name.png")); $bitmap.Dispose()
    }
}
try {
    Assert ($portBox.Text -ceq 'COM42' -and $baudBox.Text -ceq '921600') 'Saved connection not displayed'
    Assert ($portBox.Items.Contains('AUTO') -and $portBox.Items.Contains('COM7') -and $portBox.Items.Contains('COM42')) 'Port choices omit AUTO, Windows names or saved disconnected port'
    Assert (($baudBox.Items -join ',') -ceq '115200,230400,460800,921600') 'Unexpected baud choices'
    Assert ($restartNotice.Text -like '*efter appomstart*' -and $restartNotice.Text -like '*Avsluta BongoDesk*') 'Restart requirement missing'
    Assert (-not (Test-Dirty)) 'Opening connection controls marks config dirty'
    $originalSpotify=Snapshot $config.spotify; $originalUnrelated=Snapshot $config.unrelated
    $portBox.Text=' com17 '; $baudBox.SelectedItem='460800'
    Assert (Test-Dirty) 'Connection edits not tracked'
    Undo-Settings
    Assert ($portBox.Text -ceq 'COM42' -and $baudBox.Text -ceq '921600' -and -not (Test-Dirty)) 'Undo did not restore connection'
    $portBox.Text=' com17 '; $baudBox.SelectedItem='460800'
    Assert (Save-Settings) "Connection save failed: $($message.Text)"
    $fresh=Read-JsonFile $ConfigPath
    Assert ($fresh.connection.com_port -ceq 'COM17' -and $fresh.connection.baudrate -eq 460800) 'Connection not normalized/saved'
    Assert ($fresh.connection.custom_connection -ceq 'bevaras') 'Unknown connection field changed'
    Assert ((Snapshot $fresh.spotify) -ceq $originalSpotify) 'Connection-only save changed Spotify/budget fields'
    Assert ((Snapshot $fresh.unrelated) -ceq $originalUnrelated) 'Unicode/deep unknown fields changed'
    Assert ($message.Text -like '*efter appomstart*' -and -not (Test-Dirty)) 'Save falsely promises live application or remains dirty'
    foreach ($baud in @('115200','230400','460800','921600')) {
        $baudBox.SelectedItem=$baud; $portBox.Text='auto'
        Assert (Save-Settings) "Allowed baud rejected: $baud"
        $fresh=Read-JsonFile $ConfigPath
        Assert ($fresh.connection.com_port -ceq 'AUTO' -and $fresh.connection.baudrate -eq [int]$baud) "Wrong persisted baud: $baud"
    }
    # Re-read before save; preserve edits by the Python/config owner, including
    # UI-owned fields the user did not touch in this window.
    $fresh=Read-JsonFile $ConfigPath
    $fresh.spotify.client_id='externally-changed-id'
    $fresh.spotify.api_min_interval_seconds=0.75
    $fresh.spotify.unknown_budget.counter=127
    $fresh.startup.start_with_windows=$false
    $fresh.unrelated.unicode='Åäö från annan skrivare'
    Write-Fixture $fresh
    $portBox.Text='COM88'; Assert (Save-Settings) 'Save after external config change failed'
    $fresh=Read-JsonFile $ConfigPath
    Assert ($fresh.spotify.client_id -ceq 'externally-changed-id' -and $fresh.spotify.unknown_budget.counter -eq 127) 'External Spotify/budget changes overwritten'
    Assert ($fresh.spotify.api_min_interval_seconds -eq 0.75 -and $minimumBox.Text -ceq '0,75') 'Untouched API setting not preserved/refreshed'
    Assert (-not $fresh.startup.start_with_windows -and -not $startup.Checked) 'Untouched startup setting overwritten'
    Assert ($fresh.unrelated.unicode -ceq 'Åäö från annan skrivare') 'External Unicode field overwritten'
    $fresh.connection.com_port='COM81'; $fresh.connection.baudrate=230400; Write-Fixture $fresh
    $retryBox.Text='4'; Assert (Save-Settings) 'API save after external connection change failed'
    $fresh=Read-JsonFile $ConfigPath
    Assert ($fresh.connection.com_port -ceq 'COM81' -and $fresh.connection.baudrate -eq 230400) 'Untouched external connection overwritten'
    Assert ($portBox.Text -ceq 'COM81' -and $baudBox.Text -ceq '230400') 'Preserved connection not reflected in view'
    Render-Connection 'connection-saved'
    foreach ($invalidPort in @('', 'COM0', 'COM-1', '/dev/tty0', 'COM7:extra', 'AUTO-other')) {
        $before=[IO.File]::ReadAllText($ConfigPath); $portBox.Text=$invalidPort
        Assert (-not (Save-Settings)) "Invalid port accepted: $invalidPort"
        Assert ([IO.File]::ReadAllText($ConfigPath) -ceq $before) 'Rejected port changed config bytes'
        Assert ($currentPage -eq 'Inställningar' -and $errors.GetError($portBox) -ne '' -and $portBox.Focused) 'Invalid port lacks accessible error/focus'
    }
    Render-Connection 'connection-validation'
    Undo-Settings
    [void]$baudBox.Items.Add('57600'); $baudBox.SelectedItem='57600'
    $before=[IO.File]::ReadAllText($ConfigPath)
    Assert (-not (Save-Settings)) 'New unsupported baud accepted'
    Assert ([IO.File]::ReadAllText($ConfigPath) -ceq $before) 'Rejected baud changed config bytes'
    Undo-Settings
    # An older explicit value remains visible and untouched when editing only
    # another field; changing baud still requires one of the four choices.
    $fresh=Read-JsonFile $ConfigPath; $fresh.connection.baudrate=57600; Write-Fixture $fresh
    $script:loadingEdits=$true; Set-ConnectionInputs (Get-ConnectionValues $fresh)
    $script:savedEdits=Get-EditSnapshot; $script:loadingEdits=$false
    Assert ($baudBox.Text -ceq '57600') 'Older explicit baud hidden'
    $portBox.Text='COM87'; Assert (Save-Settings) 'Unrelated edit rejected because of older baud'
    Assert ((Read-JsonFile $ConfigPath).connection.baudrate -eq 57600) 'Older unchanged baud silently migrated'
    $baudBox.SelectedItem='921600'; Assert (Save-Settings) 'Supported baud selection after older baud failed'
    # A write that cannot replace the destination must keep its old bytes and
    # remove its unique temporary file. A legacy shared .tmp is not ours.
    $sentinel="$ConfigPath.tmp"; [IO.File]::WriteAllText($sentinel,'other-writer')
    $before=[IO.File]::ReadAllText($ConfigPath)
    $handle=[IO.File]::Open($ConfigPath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $replaceFailed=$false
    try { try { Write-JsonFileAtomic $ConfigPath @{ replaced=$true } } catch { $replaceFailed=$true } }
    finally { $handle.Dispose() }
    Assert ($replaceFailed) 'Exclusive destination did not exercise atomic replacement failure'
    Assert ([IO.File]::ReadAllText($ConfigPath) -ceq $before) 'Failed replacement damaged prior file'
    Assert (@(Get-ChildItem -LiteralPath $testRoot -Filter '.fixture-config.json.*.tmp' -Force).Count -eq 0) 'Unique temporary file leaked'
    Assert ([IO.File]::ReadAllText($sentinel) -ceq 'other-writer') 'Shared legacy temporary file clobbered'
    Request-PacingReset; Set-CpuDiagnosticsEnabled $true
    $fresh=Read-JsonFile $ConfigPath
    Assert ($fresh.spotify.api_reset_safety_requested_at -gt 0 -and $fresh.diagnostics.esp32_cpu_meter_enabled) 'Existing immediate actions no longer save'
    Assert ($fresh.connection.com_port -ceq 'COM87' -and $fresh.connection.baudrate -eq 921600) 'Immediate action changed connection'
    Assert ($fresh.spotify.client_id -ceq 'externally-changed-id' -and $fresh.unrelated.unicode -ceq 'Åäö från annan skrivare') 'Immediate action lost unrelated fields'
    Render-Connection 'connection-minimum' 824 611
    $form.AutoScaleMode='None'
    function Get-FontSizes($control) {
        [pscustomobject]@{ Control=$control; Size=$control.Font.Size; Style=$control.Font.Style }
        foreach ($child in $control.Controls) { Get-FontSizes $child }
    }
    $fontSizes=@(Get-FontSizes $form); $form.Scale([Drawing.SizeF]::new(1.5,1.5))
    foreach ($item in $fontSizes) { $item.Control.Font=[Drawing.Font]::new('Segoe UI',($item.Size*1.5),$item.Style) }
    Render-Connection 'connection-scale150' 1440 1000
    Write-Output "Connection settings: $script:assertions assertions passed; isolated native renders complete."
} finally {
    $script:savedEdits=Get-EditSnapshot
    $form.Close(); $form.Dispose()
}
