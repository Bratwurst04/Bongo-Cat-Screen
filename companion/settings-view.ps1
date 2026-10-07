# Dot-sourced by settings.ps1; this file owns presentation and UI events only.
# Keep disabled text readable on dark surfaces; enabled buttons retain native
# keyboard activation, focus cues, mnemonics and accessibility.
if (-not ('BongoUiButton' -as [type])) {
    Add-Type -ReferencedAssemblies System.Windows.Forms,System.Drawing -WarningAction SilentlyContinue -TypeDefinition @'
using System.Drawing;
using System.Windows.Forms;
public class BongoUiButton : Button {
    protected override void OnPaint(PaintEventArgs e) {
        if (Enabled) { base.OnPaint(e); return; }
        using (var brush = new SolidBrush(BackColor)) e.Graphics.FillRectangle(brush, ClientRectangle);
        using (var pen = new Pen(FlatAppearance.BorderColor))
            e.Graphics.DrawRectangle(pen, 0, 0, Width - 1, Height - 1);
        var flags = TextFormatFlags.VerticalCenter | TextFormatFlags.HorizontalCenter;
        if (TextAlign == ContentAlignment.MiddleLeft) flags = TextFormatFlags.VerticalCenter | TextFormatFlags.Left;
        TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle, Color.FromArgb(184,193,203), flags);
    }
}
'@
}
$script:palette = @{}
@{ Background='080A0C'; Navigation='101419'; Surface='15191E'; Input='20262D'; Border='4C555D'; Text='F2F4F7'; Muted='B8C1CB'; Accent='1ED760'; AccentDark='1B3025'; Warning='FFC14D'; Error='FF9292' }.GetEnumerator() | ForEach-Object {
    $script:palette[$_.Key] = [Drawing.ColorTranslator]::FromHtml("#$($_.Value)")
}
$form = [Windows.Forms.Form]::new()
$form.Text = 'Bongo Cat · Companion'
$form.Font = [Drawing.Font]::new('Segoe UI', 10)
$form.AutoScaleDimensions = [Drawing.SizeF]::new(7, 19); $form.AutoScaleMode = 'Font'
$form.ClientSize = [Drawing.Size]::new(960, 740); $form.MinimumSize = [Drawing.Size]::new(840, 650)
$form.StartPosition = 'CenterScreen'; $form.KeyPreview = $true
$form.BackColor = $palette.Background; $form.ForeColor = $palette.Text
Enable-DoubleBuffering $form
$toolTip = [Windows.Forms.ToolTip]::new()
$toolTip.AutoPopDelay = 15000; $toolTip.InitialDelay = 350; $toolTip.ReshowDelay = 100
$errors = [Windows.Forms.ErrorProvider]::new()
$errors.ContainerControl = $form; $errors.BlinkStyle = 'NeverBlink'

function Add-StackControl($stack, $control) {
    $row = $stack.RowCount; $stack.RowCount++
    [void]$stack.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::AutoSize))
    [void]$stack.Controls.Add($control, 0, $row)
}
function New-Stack($parent, [bool]$card = $false) {
    $stack = [Windows.Forms.TableLayoutPanel]::new()
    $stack.ColumnCount = 1; $stack.RowCount = 0
    [void]$stack.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent, 100))
    $stack.AutoSize = $true; $stack.AutoSizeMode = 'GrowAndShrink'; $stack.Dock = 'Top'
    $stack.Margin = [Windows.Forms.Padding]::new(0, 0, 0, 16)
    if ($card) { $stack.BackColor=$palette.Surface; $stack.Padding=[Windows.Forms.Padding]::new(20,16,20,16) }
    Enable-DoubleBuffering $stack
    if ($parent -is [Windows.Forms.TableLayoutPanel]) { Add-StackControl $parent $stack }
    elseif ($null -ne $parent) { [void]$parent.Controls.Add($stack) }
    return $stack
}
function Add-Text($stack, [string]$text, [float]$size=10, [string]$tone='Text', [bool]$bold=$false) {
    $label = [Windows.Forms.Label]::new()
    $label.Text=$text; $label.AutoSize=$true; $label.Dock='Fill'
    $style = if ($bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
    $label.Font=[Drawing.Font]::new('Segoe UI',$size,$style); $label.ForeColor=$palette[$tone]
    $label.Margin=[Windows.Forms.Padding]::new(0,0,0,9)
    Add-StackControl $stack $label
    return $label
}
function New-Button([string]$text, [bool]$primary=$false) {
    $button = [BongoUiButton]::new()
    $button.Text=$text; $button.AutoSize=$true; $button.AutoSizeMode='GrowAndShrink'
    $button.MinimumSize=[Drawing.Size]::new(112,38); $button.Padding=[Windows.Forms.Padding]::new(12,4,12,4)
    $button.FlatStyle='Flat'; $button.FlatAppearance.BorderColor=$palette.Border
    $button.BackColor=if ($primary) { $palette.Accent } else { $palette.Input }
    $button.ForeColor=if ($primary) { $palette.Background } else { $palette.Text }
    $button.FlatAppearance.MouseOverBackColor=if ($primary) { [Drawing.ColorTranslator]::FromHtml('#53E487') } else { $palette.AccentDark }
    $button.FlatAppearance.MouseDownBackColor=if ($primary) { [Drawing.ColorTranslator]::FromHtml('#17B951') } else { $palette.Navigation }
    $button.UseVisualStyleBackColor=$false
    return $button
}
function Add-Card($page,[string]$caption) {
    $card=New-Stack $page $true
    $null=Add-Text $card $caption 9 'Muted' $true
    return $card
}
function Format-Wait([double]$seconds) {
    if ($seconds -lt 60) { return "$([math]::Ceiling([math]::Max(0,$seconds))) s" }
    $minutes=[int][math]::Ceiling($seconds/60)
    if ($minutes -lt 60) { return "$minutes min" }
    $hours=[int][math]::Floor($minutes/60); $remaining=$minutes%60
    if ($remaining -eq 0) { return "$hours h" }
    return "$hours h $remaining min"
}
function Format-Percent($value) {
    if ($null -eq $value) { return '—' }
    return ('{0:0.#}' -f [double]$value)
}

$shell=[Windows.Forms.TableLayoutPanel]::new()
$shell.Dock='Fill'; $shell.Margin=[Windows.Forms.Padding]::new(0); $shell.ColumnCount=2; $shell.RowCount=1
[void]$shell.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Absolute,184))
[void]$shell.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent,100))
[void]$shell.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Percent,100))
[void]$form.Controls.Add($shell)
$navigation=[Windows.Forms.Panel]::new()
$navigation.Dock='Fill'; $navigation.BackColor=$palette.Navigation; $navigation.Margin=[Windows.Forms.Padding]::new(0)
$navigation.Padding=[Windows.Forms.Padding]::new(16,20,16,20)
[void]$shell.Controls.Add($navigation,0,0)
$brand=New-Stack $navigation
$catImage=$null
$imagePath=Join-Path $PSScriptRoot 'ui\bongo.png'
if (Test-Path -LiteralPath $imagePath) {
    $catImage=[Drawing.Image]::FromFile($imagePath)
    $picture=[Windows.Forms.PictureBox]::new()
    $picture.Size=[Drawing.Size]::new(128,128)
    $picture.Anchor='Top'; $picture.TabStop=$false
    $picture.Add_Paint({
        $_.Graphics.InterpolationMode=[Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
        $_.Graphics.PixelOffsetMode=[Drawing.Drawing2D.PixelOffsetMode]::Half
        $_.Graphics.DrawImage($catImage,[Drawing.Rectangle]::new(0,0,$this.Width,$this.Height))
    })
    Add-StackControl $brand $picture
}
$null=Add-Text $brand 'BONGO CAT' 14 'Text' $true
$null=Add-Text $brand 'Companion för Windows' 9 'Muted'
$navStack=New-Stack $brand
$navStack.Margin=[Windows.Forms.Padding]::new(0,24,0,0)
$script:navButtons=@{}
foreach ($name in @('Översikt','Inställningar','Diagnostik')) {
    $button=New-Button $name
    $button.Dock='Fill'; $button.TextAlign='MiddleLeft'; $button.Tag=$name
    $button.Margin=[Windows.Forms.Padding]::new(0,0,0,10); $button.AccessibleName=$name
    $button.Add_Click({ Select-Page $this.Tag })
    Add-StackControl $navStack $button
    $script:navButtons[$name]=$button
}
$navFoot=[Windows.Forms.Label]::new()
$navFoot.Dock='Bottom'; $navFoot.Height=52; $navFoot.Text="DIN SKÄRM`r`nBongo · Spelare · Fokus"
$navFoot.Font=[Drawing.Font]::new('Segoe UI',9); $navFoot.ForeColor=$palette.Muted
[void]$navigation.Controls.Add($navFoot)

$main=[Windows.Forms.TableLayoutPanel]::new()
$main.Dock='Fill'; $main.Margin=[Windows.Forms.Padding]::new(0); $main.ColumnCount=1; $main.RowCount=3
[void]$main.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent,100))
[void]$main.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::AutoSize))
[void]$main.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Percent,100))
[void]$main.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::AutoSize))
[void]$shell.Controls.Add($main,1,0)
$header=New-Stack $null
$header.Padding=[Windows.Forms.Padding]::new(28,24,28,0); $header.Margin=[Windows.Forms.Padding]::new(0)
$heading=Add-Text $header '' 21 'Text' $true
$subtitle=Add-Text $header '' 10 'Muted'
[void]$main.Controls.Add($header,0,0)
$viewport=[Windows.Forms.Panel]::new()
$viewport.Dock='Fill'; $viewport.AutoScroll=$true; $viewport.Margin=[Windows.Forms.Padding]::new(0)
$viewport.Padding=[Windows.Forms.Padding]::new(28,16,28,12)
Enable-DoubleBuffering $viewport
[void]$main.Controls.Add($viewport,0,1)
$script:pages=@{}
foreach ($name in @('Översikt','Inställningar','Diagnostik')) {
    $page=New-Stack $viewport
    $page.Visible=$false; $page.Margin=[Windows.Forms.Padding]::new(0)
    $script:pages[$name]=$page
}
$footer=New-Stack $null
$footer.BackColor=$palette.Navigation; $footer.Padding=[Windows.Forms.Padding]::new(28,12,28,12)
$footer.Margin=[Windows.Forms.Padding]::new(0); $footer.Dock='Top'
$message=Add-Text $footer 'Alla ändringar sparade' 9 'Muted'
$actions=[Windows.Forms.TableLayoutPanel]::new()
$actions.AutoSize=$true; $actions.AutoSizeMode='GrowAndShrink'; $actions.Dock='Top'
$actions.ColumnCount=3; $actions.RowCount=1
[void]$actions.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent,100))
[void]$actions.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::AutoSize))
[void]$actions.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::AutoSize))
[void]$actions.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::AutoSize))
$actions.Margin=[Windows.Forms.Padding]::new(0)
$save=New-Button '&Spara ändringar' $true
$undo=New-Button '&Ångra ändringar'
$save.Margin=[Windows.Forms.Padding]::new(12,0,0,0); $undo.Margin=[Windows.Forms.Padding]::new(0)
[void]$actions.Controls.Add($undo,1,0); [void]$actions.Controls.Add($save,2,0)
Add-StackControl $footer $actions
[void]$main.Controls.Add($footer,0,2)

$overview=$pages['Översikt']
$connectionCard=Add-Card $overview 'SKÄRMANSLUTNING'
$connectionTitle=Add-Text $connectionCard 'Väntar på status…' 18 'Muted' $true
$connectionDetail=Add-Text $connectionCard 'Companionens status visas här när den är tillgänglig.' 10 'Muted'
$spotifyCard=Add-Card $overview 'SPOTIFY'
$spotifyTitle=Add-Text $spotifyCard 'Väntar på musikstatus…' 18 'Text' $true
$spotifyDetail=Add-Text $spotifyCard '' 10 'Muted'
$spotifyNotice=Add-Text $spotifyCard '' 10 'Warning'
$pcSummary=Add-Text $overview 'Datorn · väntar på statistik.' 9 'Muted'
$null=Add-Text $overview 'Tema och Fokus-tider ställer du in på själva skärmen.' 9 'Muted'

$settings=$pages['Inställningar']
$general=Add-Card $settings 'WINDOWS'
$startup=[Windows.Forms.CheckBox]::new()
$startup.Text='Starta BongoDesk när jag loggar in i Windows'; $startup.AutoSize=$true; $startup.Dock='Fill'
$startup.Checked=[bool]$config.startup.start_with_windows; $startup.Margin=[Windows.Forms.Padding]::new(0,0,0,9)
Add-StackControl $general $startup
$null=Add-Text $general 'Companion körs i bakgrunden och nås via ikonen vid klockan.' 9 'Muted'
$connectCard=Add-Card $settings 'SPOTIFY CONNECT'
$null=Add-Text $connectCard 'Musik på en annan enhet' 13 'Text' $true
$null=Add-Text $connectCard 'Kortare intervall ger snabbare musikuppdateringar och fler Spotify-anrop. Spotify kan kräva längre väntan. Standard är 15 sekunder.' 10 'Muted'
$script:fieldSpecs=[Collections.ArrayList]::new()
function Add-Field($card,[string]$key,[string]$caption,[string]$help,[string]$value,[string]$unit) {
    $row=[Windows.Forms.TableLayoutPanel]::new()
    $row.AutoSize=$true; $row.Dock='Fill'; $row.ColumnCount=3; $row.RowCount=1
    [void]$row.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent,100))
    [void]$row.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Absolute,88))
    [void]$row.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Absolute,86))
    $row.Margin=[Windows.Forms.Padding]::new(0,0,0,12)
    $label=[Windows.Forms.Label]::new()
    $label.Text=$caption; $label.AutoSize=$true; $label.Dock='Fill'; $label.TextAlign='MiddleLeft'
    $label.Margin=[Windows.Forms.Padding]::new(0,4,12,0)
    $input=[Windows.Forms.TextBox]::new()
    $input.Text=$value
    if ($key -ne 'artwork_retry_attempts') {
        try { $input.Text=(Parse-Decimal $value).ToString('0.################',[Globalization.CultureInfo]::GetCultureInfo('sv-SE')) } catch { }
    }
    $input.Dock='Fill'; $input.BackColor=$palette.Input; $input.ForeColor=$palette.Text
    $input.BorderStyle='FixedSingle'; $input.Margin=[Windows.Forms.Padding]::new(0,4,18,0)
    $input.AccessibleName=$caption; $input.AccessibleDescription=$help
    $unitLabel=[Windows.Forms.Label]::new()
    $unitLabel.Text=$unit; $unitLabel.AutoSize=$true; $unitLabel.Dock='Fill'; $unitLabel.TextAlign='MiddleLeft'
    $unitLabel.ForeColor=$palette.Muted; $unitLabel.Margin=[Windows.Forms.Padding]::new(0,4,0,0)
    [void]$row.Controls.Add($label,0,0); [void]$row.Controls.Add($input,1,0); [void]$row.Controls.Add($unitLabel,2,0)
    Add-StackControl $card $row
    $toolTip.SetToolTip($label,$help); $toolTip.SetToolTip($input,$help)
    [void]$script:fieldSpecs.Add([pscustomobject]@{ Key=$key; Caption=$caption; Control=$input })
    return $input
}
$connectBox=Add-Field $connectCard 'api_only_poll_interval_seconds' 'Uppdateringsintervall' '10–120 s. Säkerhetsgräns och Spotify-väntan kan förlänga intervallet. Ett extra prov nära låtslut kan göras en gång per spår.' (Config-Value 'api_only_poll_interval_seconds' '15') 'sekunder'
$advancedToggle=New-Button 'Visa avancerade inställningar  +'
$advancedToggle.Anchor='Left'; $advancedToggle.Margin=[Windows.Forms.Padding]::new(0,0,0,8)
$advancedToggle.AccessibleName='Avancerade inställningar'
Add-StackControl $settings $advancedToggle
$advancedContent=New-Stack $settings
$advancedContent.Visible=$false; $script:advancedExpanded=$false
$apiCard=Add-Card $advancedContent 'SPOTIFY · API-INTERVALL'
$null=Add-Text $apiCard 'Den automatiska säkerhetsgränsen gäller alltid' 12 'Text' $true
$null=Add-Text $apiCard 'Dessa värden styr API-takten. Windows lokala Spotify-session behöver ingen regelbunden Connect-läsning. Spotify kan kräva längre väntan.' 10 'Muted'
$connectEstimate=Add-Text $apiCard '' 9 'Muted'
$minimumBox=Add-Field $apiCard 'api_min_interval_seconds' 'Snabbast tillåtet' 'Lägsta adaptiva API-intervall, minst 0,5 s. Ett teoretiskt tak, inte verklig anropsfrekvens.' (Config-Value 'api_min_interval_seconds' '1') 'sekunder'
$initialBox=Add-Field $apiCard 'api_initial_interval_seconds' 'Vanlig API-gräns' 'Startintervall. Minst Snabbast tillåtet och högst den konfigurerade maxgränsen (normalt 30 s).' (Config-Value 'api_initial_interval_seconds' '3') 'sekunder'
$idleBox=Add-Field $apiCard 'api_idle_interval_seconds' 'API-gräns vid paus' 'Minst Vanlig API-gräns, högst 300 s. Connect, säkerhetsgräns och Retry-After kan ge längre väntan.' (Config-Value 'api_idle_interval_seconds' '10') 'sekunder'
$null=Add-Text $apiCard 'Ordning: snabbast ≤ vanlig ≤ paus. Komma eller punkt fungerar för decimaler.' 9 'Muted'
$artworkCard=Add-Card $advancedContent 'ALBUMOMSLAG'
$retryBox=Add-Field $artworkCard 'artwork_retry_attempts' 'Hämtningsförsök för omslag' '1–5 försök att hämta ett saknat albumomslag. Detta är inte antalet seriella omförsök.' (Config-Value 'artwork_retry_attempts' '5') 'försök'

function Set-AdvancedExpanded([bool]$expanded) {
    $hadFocus=$advancedContent.ContainsFocus
    $script:advancedExpanded=$expanded; $advancedContent.Visible=$expanded
    $advancedToggle.Text=if ($expanded) { 'Dölj avancerade inställningar  −' } else { 'Visa avancerade inställningar  +' }
    $advancedToggle.AccessibleDescription=if ($expanded) { 'Öppen. Aktivera för att dölja API-intervall och omslagsförsök.' } else { 'Stängd. Aktivera för att visa API-intervall och omslagsförsök.' }
    $settings.PerformLayout(); $viewport.PerformLayout()
    if (-not $expanded -and $hadFocus) { [void]$advancedToggle.Focus() }
}
$advancedToggle.Add_Click({ Set-AdvancedExpanded (-not $script:advancedExpanded) })

$diagnosticPage=$pages['Diagnostik']
$alertCard=Add-Card $diagnosticPage 'AKTUELLT LÄGE'; $diagnosticAlert=Add-Text $alertCard 'Väntar på status…' 11 'Muted'
$apiDiagnostics=Add-Card $diagnosticPage 'SPOTIFY API'; $script:diagnosticRows=@{}
function Add-DiagnosticRow($card,[string]$key,[string]$caption,[string]$help) {
    $null=Add-Text $card $caption 9 'Muted' $true
    $value=Add-Text $card '—' 10
    $value.Margin=[Windows.Forms.Padding]::new(0,0,0,17)
    $toolTip.SetToolTip($value,$help); $script:diagnosticRows[$key]=$value
}
Add-DiagnosticRow $apiDiagnostics 'Api' 'Registrerade HTTP 429' 'Verkliga HTTP 429-svar. Sparad cooldown räknas inte igen. Äldre historia före räknaren kan saknas.'
Add-DiagnosticRow $apiDiagnostics 'Windows' 'Senaste gränsträffar' 'Rullande tidsfönster. Den totala räknaren rensas inte när de löper ut.'
Add-DiagnosticRow $apiDiagnostics 'Adaptive' 'Uppdatering och säkerhetsgräns' 'Regelbunden Connect-läsning följer det längsta av vald tid, säkerhetsgräns, paus och kvotåterhämtning. Retry-After respekteras alltid.'
Add-DiagnosticRow $apiDiagnostics 'Change' 'Senaste automatiska ändring' 'Förändring av den adaptiva API-takten och dess orsak.'
Add-DiagnosticRow $apiDiagnostics 'Calls' 'Verkliga API-anrop' 'Anrop under denna körning. Noll under 30 sekunder kan vara normalt.'
$safetyReset=New-Button 'Återställ inlärd API-gräns…'; Add-StackControl $apiDiagnostics $safetyReset
$null=Add-Text $apiDiagnostics 'Utgår från sparat Snabbast tillåtet-värde. Spotify-väntan gäller fortfarande. Ändras direkt.' 9 'Muted'
$resetMessage=Add-Text $apiDiagnostics '' 9 'Muted'
$resetMessage.Visible=$false
$espDiagnostics=Add-Card $diagnosticPage 'SKÄRMEN · ESP32'
Add-DiagnosticRow $espDiagnostics 'Connection' 'Anslutning' 'Seriell kontakt är inte samma sak som bekräftad sömn eller väckning.'
Add-DiagnosticRow $espDiagnostics 'Heap' 'Arbetsminne' 'Heap, lägsta sedan start och eventuell PSRAM. Värdet kommer från skärmen.'
Add-DiagnosticRow $espDiagnostics 'Cpu' 'CPU-aktivitet' 'Valfri grov uppskattning från FreeRTOS-idleticks. Inte en exakt profilerare per uppgift.'
$cpuToggle=New-Button 'Aktivera CPU-mätning'; Add-StackControl $espDiagnostics $cpuToggle
$cpuMessage=Add-Text $espDiagnostics 'Grov uppskattning. Ändras direkt och påverkas inte av Spara eller Ångra.' 9 'Muted'
$hostDiagnostics=Add-Card $diagnosticPage 'WINDOWS · RESURSER'; $hostDetail=Add-Text $hostDiagnostics 'Väntar på datorns statistik.'
$null=Add-Text $hostDiagnostics 'Exportera en diagnostikrapport via BongoDesk-ikonen vid klockan: Export diagnostics ZIP…' 9 'Muted'

function Select-Page([string]$name) {
    $script:currentPage=$name; $viewport.SuspendLayout()
    foreach ($key in $pages.Keys) {
        $pages[$key].Visible=($key -eq $name)
        $navButtons[$key].BackColor=if ($key -eq $name) { $palette.AccentDark } else { $palette.Navigation }
        $navButtons[$key].ForeColor=if ($key -eq $name) { $palette.Accent } else { $palette.Text }
        $navButtons[$key].FlatAppearance.BorderColor=if ($key -eq $name) { $palette.Accent } else { $palette.Navigation }
        $navButtons[$key].AccessibleDescription=if ($key -eq $name) { 'Aktuell sida' } else { 'Öppna sidan' }
    }
    switch ($name) {
        'Översikt' { $heading.Text='Din Bongo, i ett ögonkast'; $subtitle.Text='Skärmen och musiken, samlat här.' }
        'Inställningar' { $heading.Text='Gör Bongo till din'; $subtitle.Text='Ändringar används när du sparar. Ctrl+S sparar, Ångra återställer.' }
        'Diagnostik' { $heading.Text='Se vad som händer'; $subtitle.Text='Livevärden från Spotify, Windows och skärmen. Uppdateras varje sekund.' }
    }
    $viewport.AutoScrollPosition=[Drawing.Point]::Empty; $viewport.ResumeLayout($true)
    Update-FooterVisibility
}
function Update-FooterVisibility([bool]$restoreFocus=$false) {
    $show=($script:currentPage -eq 'Inställningar' -or (Test-Dirty))
    $hadFocus=$footer.ContainsFocus
    $footer.Visible=$show
    $main.PerformLayout()
    if (-not $show -and ($hadFocus -or $restoreFocus)) { [void]$navButtons[$script:currentPage].Focus() }
}
function Get-EditSnapshot {
    $snapshot=@{ startup=[bool]$startup.Checked }
    foreach ($field in $fieldSpecs) { $snapshot[$field.Key]=$field.Control.Text }
    return $snapshot
}
function Test-Dirty {
    if ($null -eq $script:savedEdits) { return $false }
    $current=Get-EditSnapshot
    foreach ($key in $current.Keys) { if ($current[$key] -cne $script:savedEdits[$key]) { return $true } }
    return $false
}
function Update-EditState {
    $hadFooterFocus=$footer.ContainsFocus
    $script:dirty=Test-Dirty; $save.Enabled=$script:dirty; $undo.Enabled=$script:dirty
    $save.BackColor=if ($script:dirty) { $palette.Accent } else { $palette.Input }
    $save.ForeColor=if ($script:dirty) { $palette.Background } else { $palette.Muted }
    if (-not $script:loadingEdits) {
        $errors.Clear(); $message.ForeColor=$palette.Muted
        $message.Text=if ($script:dirty) { 'Osparade ändringar. Spara för att använda dem.' } else { 'Alla ändringar sparade' }
    }
    if ($null -ne $script:lastInfo) { $safetyReset.Enabled=(-not $script:dirty -and $null -ne $script:lastInfo.media.spotify.pacing -and -not $script:statusStale) }
    try {
        $seconds=Parse-Decimal $connectBox.Text
        if ($seconds -ge 10 -and $seconds -le 120) { $connectEstimate.Text="Cirka $([math]::Round(86400/$seconds)) grundfrågor per dygn vid ständig drift. Skärmen räknar tiden mellan uppdateringar." }
        else { $connectEstimate.Text='Välj ett intervall mellan 10 och 120 sekunder.' }
    } catch { $connectEstimate.Text='Ange intervallet i sekunder.' }
    Update-FooterVisibility $hadFooterFocus
}
function Save-Settings {
    $errors.Clear(); $invalid=$null
    try {
        $values=@{}
        foreach ($field in $fieldSpecs) {
            $invalid=$field
            try { $values[$field.Key]=if ($field.Key -eq 'artwork_retry_attempts') { [int]::Parse($field.Control.Text.Trim()) } else { Parse-Decimal $field.Control.Text } }
            catch { throw "Ange ett giltigt tal i fältet $($field.Caption)." }
        }
        $fresh=Read-JsonFile $ConfigPath
        if ($null -eq $fresh) { $invalid=$null; throw 'Kunde inte läsa inställningsfilen igen. Inget har sparats.' }
        if ($null -eq $fresh.spotify) { $fresh | Add-Member -NotePropertyName spotify -NotePropertyValue ([pscustomobject]@{}) }
        if ($null -eq $fresh.startup) { $fresh | Add-Member -NotePropertyName startup -NotePropertyValue ([pscustomobject]@{}) }
        $maximum=if ($null -ne $fresh.spotify.api_max_interval_seconds) { [double]$fresh.spotify.api_max_interval_seconds } else { 30.0 }
        $minimum=$values.api_min_interval_seconds; $initial=$values.api_initial_interval_seconds
        $idle=$values.api_idle_interval_seconds; $connect=$values.api_only_poll_interval_seconds; $retries=$values.artwork_retry_attempts
        $badKey=$null; $errorText=''
        if ($connect -lt 10 -or $connect -gt 120) { $badKey='api_only_poll_interval_seconds'; $errorText='Uppdateringsintervallet ska vara 10–120 sekunder.' }
        elseif ($retries -lt 1 -or $retries -gt 5) { $badKey='artwork_retry_attempts'; $errorText='Välj 1–5 hämtningsförsök för omslag.' }
        elseif ($minimum -lt 0.5 -or $minimum -gt $maximum) { $badKey='api_min_interval_seconds'; $errorText="Snabbast tillåtet ska vara 0,5–$(Format-Seconds $maximum) sekunder." }
        elseif ($initial -lt $minimum -or $initial -gt $maximum) { $badKey='api_initial_interval_seconds'; $errorText="Vanlig API-gräns ska vara minst Snabbast tillåtet och högst $(Format-Seconds $maximum) sekunder." }
        elseif ($idle -lt $initial -or $idle -gt 300) { $badKey='api_idle_interval_seconds'; $errorText='API-gräns vid paus ska vara minst Vanlig API-gräns och högst 300 sekunder.' }
        if ($null -ne $badKey) { $invalid=$fieldSpecs | Where-Object Key -eq $badKey | Select-Object -First 1; throw $errorText }
        $invalid=$null
        foreach ($key in $values.Keys) { $fresh.spotify | Add-Member -NotePropertyName $key -NotePropertyValue $values[$key] -Force }
        $fresh.startup | Add-Member start_with_windows ([bool]$startup.Checked) -Force
        $temporary="$ConfigPath.tmp"
        [IO.File]::WriteAllText($temporary,($fresh | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $ConfigPath -Force
        $script:savedEdits=Get-EditSnapshot; Update-EditState
        $message.ForeColor=$palette.Accent; $message.Text='Sparat. Companion använder de nya värdena automatiskt.'
        return $true
    } catch {
        if ($null -ne $invalid) {
            Select-Page 'Inställningar'
            if ($advancedContent.Contains($invalid.Control)) { Set-AdvancedExpanded $true }
            $errors.SetError($invalid.Control,$_.Exception.Message)
            $viewport.ScrollControlIntoView($invalid.Control); [void]$invalid.Control.Focus(); $invalid.Control.SelectAll()
        }
        $message.ForeColor=$palette.Error; $message.Text=$_.Exception.Message
        return $false
    }
}
function Undo-Settings {
    $script:loadingEdits=$true
    foreach ($field in $fieldSpecs) { $field.Control.Text=$script:savedEdits[$field.Key] }
    $startup.Checked=[bool]$script:savedEdits.startup; $script:loadingEdits=$false
    Update-EditState; $message.Text='Ändringarna har ångrats. Sparade värden visas.'
}
$script:savedEdits=Get-EditSnapshot
$script:loadingEdits=$false; $script:lastInfo=$null; $script:cpuPending=$null; $script:statusStale=$true
foreach ($field in $fieldSpecs) { $field.Control.Add_TextChanged({ Update-EditState }) }
$startup.Add_CheckedChanged({ Update-EditState })
$save.Add_Click({ $null=Save-Settings }); $undo.Add_Click({ Undo-Settings })
$form.Add_KeyDown({
    if ($_.Control -and $_.KeyCode -eq 'S') { $null=Save-Settings; $_.SuppressKeyPress=$true }
    if ($_.KeyCode -eq 'Escape') { $form.Close(); $_.SuppressKeyPress=$true }
})
function Request-SaveChoice {
    return [Windows.Forms.MessageBox]::Show($form,'Du har osparade ändringar. Vill du spara dem innan fönstret stängs?','Bongo Cat','YesNoCancel','Question')
}
function Confirm-Close {
    if (-not (Test-Dirty)) { return $true }
    $answer=Request-SaveChoice
    if ($answer -eq 'Cancel') { return $false }
    if ($answer -eq 'Yes') { return (Save-Settings) }
    return $true
}
$form.Add_FormClosing({ if (-not (Confirm-Close)) { $_.Cancel=$true } })
function Request-PacingChoice {
    return [Windows.Forms.MessageBox]::Show($form,'Den inlärda säkerhetsgränsen återställs till ditt sparade Snabbast tillåtet-värde. Fler API-anrop kan öka risken för en ny Spotify-gräns. Pågående Spotify-väntan (Retry-After) respekteras fortfarande. Fortsätta?','Återställ API-gräns','YesNo','Warning')
}
$safetyReset.Add_Click({
    $answer=Request-PacingChoice
    if ($answer -eq 'Yes') {
        try { Request-PacingReset; $resetMessage.ForeColor=$palette.Accent; $resetMessage.Text='Återställning begärd. Se nästa automatiska ändring ovan.' }
        catch { $resetMessage.ForeColor=$palette.Error; $resetMessage.Text="Kunde inte återställa API-gränsen: $($_.Exception.Message)" }
        $resetMessage.Visible=$true
    }
})
$cpuToggle.Add_Click({
    try {
        $target=-not [bool]$script:lastInfo.esp32.cpu_meter_enabled
        Set-CpuDiagnosticsEnabled $target
        $script:cpuPending=[pscustomobject]@{ Target=$target; At=(Get-UnixTime) }
        $cpuToggle.Enabled=$false; $cpuMessage.ForeColor=$palette.Muted
        $cpuMessage.Text='Ändringen är sparad. Väntar på bekräftelse från skärmen…'
    } catch { $cpuMessage.ForeColor=$palette.Error; $cpuMessage.Text="Kunde inte ändra CPU-mätningen: $($_.Exception.Message)" }
})

function Update-LiveStatus {
    $info=Read-JsonFile $StatusPath; $script:lastInfo=$info
    $fileAge=if (Test-Path -LiteralPath $StatusPath) { ([DateTime]::UtcNow-(Get-Item -LiteralPath $StatusPath).LastWriteTimeUtc).TotalSeconds } else { [double]::PositiveInfinity }
    $script:statusStale=($null -eq $info -or $fileAge -gt 15)
    if ($script:statusStale) {
        $connectionTitle.ForeColor=$palette.Warning
        Set-ControlTextIfChanged $connectionTitle $(if ($null -eq $info) { 'Väntar på companion' } else { 'Status uppdateras inte' })
        Set-ControlTextIfChanged $connectionDetail 'Ingen färsk status från BongoDesk. Kontrollera att companion körs via ikonen vid klockan.'
        Set-ControlTextIfChanged $spotifyTitle 'Musikstatus saknas'
        Set-ControlTextIfChanged $spotifyDetail 'Aktuell Spotify-källa kan inte visas förrän companion rapporterar igen.'
        Set-ControlTextIfChanged $spotifyNotice ''; $spotifyNotice.Visible=$false
        Set-ControlTextIfChanged $pcSummary 'Datorn · ingen aktuell statistik.'
        Set-ControlTextIfChanged $diagnosticAlert 'Ingen färsk status från companion. Tidigare mätvärden visas inte som aktuella.'
        $diagnosticAlert.ForeColor=$palette.Warning
        foreach ($row in $diagnosticRows.Values) { Set-ControlTextIfChanged $row '—' }
        Set-ControlTextIfChanged $hostDetail 'Ingen aktuell statistik.'
        $cpuToggle.Enabled=$false; $safetyReset.Enabled=$false
        return
    }
    $esp32=$info.esp32
    if (-not [bool]$esp32.connected) {
        $connectionTitle.ForeColor=$palette.Warning
        Set-ControlTextIfChanged $connectionTitle 'Ingen kontakt med skärmen'
        Set-ControlTextIfChanged $connectionDetail 'Kontrollera USB-kabeln. Anslutningen hanteras av companion. Skärmens sömnläge rapporteras inte separat.'
    } elseif ($null -eq $esp32.status_age_seconds) {
        $connectionTitle.ForeColor=$palette.Warning
        Set-ControlTextIfChanged $connectionTitle 'Väntar på skärmens svar'
        Set-ControlTextIfChanged $connectionDetail 'Serieporten är öppen. Skärmens första status har ännu inte kommit.'
    } elseif ([double]$esp32.status_age_seconds -gt 20) {
        $connectionTitle.ForeColor=$palette.Warning
        Set-ControlTextIfChanged $connectionTitle 'Skärmens status är fördröjd'
        Set-ControlTextIfChanged $connectionDetail "Serieporten är öppen. Senaste svar: $(Format-Age ([double]$esp32.status_age_seconds)). Sömnläge kan inte avgöras från detta."
    } else {
        $connectionTitle.ForeColor=$palette.Accent
        Set-ControlTextIfChanged $connectionTitle 'Ansluten till skärmen'
        Set-ControlTextIfChanged $connectionDetail "Senaste kontakt: $(Format-Age ([double]$esp32.status_age_seconds)). Companion körs i bakgrunden."
    }
    $spotify=$info.media.spotify
    switch ("$($info.media.current_source)") {
        'windows_spotify' {
            Set-ControlTextIfChanged $spotifyTitle 'Spotify på den här datorn'
            Set-ControlTextIfChanged $spotifyDetail 'Musikstatus hämtas från Spotify på den här datorn.'
        }
        'spotify_api' {
            Set-ControlTextIfChanged $spotifyTitle $(if ("$($spotify.state)" -eq 'rate_limited') { 'Spotify Connect väntar' } elseif ([bool]$info.media.api_only_idle) { 'Connect väntar på uppspelning' } else { 'Spotify via Connect' })
            $detail='Musikstatus hämtas från Spotify på en annan enhet.'
            Set-ControlTextIfChanged $spotifyDetail $detail
            if ("$($spotify.state)" -eq 'rate_limited') { Set-ControlTextIfChanged $spotifyDetail 'Musikstatus från en annan enhet återkommer när Spotifys väntetid är över.' }
        }
        default {
            Set-ControlTextIfChanged $spotifyTitle 'Ingen aktiv Spotify-källa'
            $detail=switch ("$($spotify.state)") {
                'not_configured' { 'Öppna Spotify på datorn för att använda Windows-sessionen. Spotify Connect är inte konfigurerat.' }
                'not_linked' { 'Windows-sessionen kan användas när Spotify är öppet. Spotify Connect-kontot är inte länkat.' }
                default { 'Väntar på musikstatus. Öppna Spotify eller starta musik på en ansluten enhet.' }
            }
            Set-ControlTextIfChanged $spotifyDetail $detail
            if ("$($spotify.state)" -eq 'rate_limited') {
                Set-ControlTextIfChanged $spotifyTitle 'Spotify Connect väntar'
                Set-ControlTextIfChanged $spotifyDetail 'Musikstatus från en annan enhet återkommer när Spotifys väntetid är över.'
            }
        }
    }
    $notice=''
    if ("$($spotify.state)" -eq 'rate_limited') {
        $notice="Spotify Connect väntar: cirka $(Format-Wait ([double]$spotify.retry_remaining_seconds)) kvar. Uppdateringarna återupptas automatiskt efter väntan."
        if ("$($info.media.current_source)" -eq 'windows_spotify') { $notice+=' Windows-sessionen används fortfarande.' }
    } elseif ([double]$spotify.pacing.quota_poll_floor_seconds -gt 0) {
        $notice='Spotify återhämtar sig efter en API-gräns. Musikuppdateringarna kan ta längre tid.'
    }
    Set-ControlTextIfChanged $spotifyNotice $notice; $spotifyNotice.Visible=($notice -ne '')
    Set-ControlTextIfChanged $pcSummary "Datorn · $(Format-Percent $info.system_cpu_percent) % CPU · $([math]::Round(([double]$info.system_memory_available_mib/1024),1)) GiB RAM ledigt av $([math]::Round(([double]$info.system_memory_total_mib/1024),1)) GiB"
    Set-ControlTextIfChanged $hostDetail "Datorn: $($info.system_cpu_percent) % CPU, $($info.system_ram_percent) % RAM.`r`nBongoDesk: $($info.app_cpu_percent) % av hela datorns CPU-kapacitet; $($info.app_cpu_percent_one_core) % av en logisk kärna. $($info.app_memory_mib) MiB RAM. ESP32 räknas inte in."
    $values=Get-DiagnosticValues $info
    foreach ($key in $diagnosticRows.Keys) { Set-ControlTextIfChanged $diagnosticRows[$key] $values.$key }
    Set-ControlTextIfChanged $diagnosticAlert $values.Alert
    $diagnosticAlert.ForeColor=if ($values.HasLimit) { $palette.Warning } else { $palette.Muted }
    Set-ControlTextIfChanged $cpuToggle $(if ($values.CpuEnabled) { 'Stäng av CPU-mätning' } else { 'Aktivera CPU-mätning' })
    $deviceFresh=[bool]$esp32.connected -and $null -ne $esp32.status_age_seconds -and [double]$esp32.status_age_seconds -le 20
    if (-not $deviceFresh) {
        Set-ControlTextIfChanged $diagnosticRows.Heap 'Ingen aktuell minnesmätning från skärmen.'
        Set-ControlTextIfChanged $diagnosticRows.Cpu 'Ingen aktuell CPU-mätning från skärmen.'
    }
    if ($null -ne $script:cpuPending) {
        if ($deviceFresh -and $values.CpuEnabled -eq $script:cpuPending.Target) {
            $script:cpuPending=$null; $cpuMessage.ForeColor=$palette.Accent
            Set-ControlTextIfChanged $cpuMessage 'Skärmen har bekräftat ändringen. CPU-mätningen är en grov uppskattning.'
        } elseif ((Get-UnixTime)-$script:cpuPending.At -gt 15) {
            $script:cpuPending=$null; $cpuMessage.ForeColor=$palette.Warning
            Set-ControlTextIfChanged $cpuMessage 'Inställningen är sparad, men skärmen har inte bekräftat den ännu. Kontrollera anslutningen.'
        }
    }
    $cpuToggle.Enabled=($deviceFresh -and $null -eq $script:cpuPending)
    $safetyReset.Enabled=(-not (Test-Dirty) -and $null -ne $spotify.pacing)
    $navButtons['Diagnostik'].Text=if ($values.HasLimit) { 'Diagnostik  !' } else { 'Diagnostik' }
}

$timer=[Windows.Forms.Timer]::new(); $timer.Interval=1000
$timer.Add_Tick({ Update-LiveStatus })
$form.Add_FormClosed({
    $timer.Stop(); $timer.Dispose(); $errors.Dispose(); $toolTip.Dispose()
    if ($null -ne $catImage) { $catImage.Dispose() }
})
$form.Add_Shown({
    $area=[Windows.Forms.Screen]::FromControl($form).WorkingArea
    $form.Size=[Drawing.Size]::new([math]::Min($form.Width,$area.Width),[math]::Min($form.Height,$area.Height))
    $form.PerformLayout()
})
Set-AdvancedExpanded $false
Select-Page 'Översikt'; Update-EditState; Update-LiveStatus
$timer.Start()
[void]$form.ShowDialog()
