param([Parameter(Mandatory=$true)][string]$RequestFile,
      [Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$request = Get-Content -LiteralPath $RequestFile -Raw -Encoding UTF8 | ConvertFrom-Json
$settings = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'tts-settings.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$voiceName = $settings.voice
$rate = [int]$settings.rate
$prosody = [bool]$settings.prosody
if ($request.PSObject.Properties.Name -contains 'voice') { $voiceName = $request.voice }
if ($request.PSObject.Properties.Name -contains 'rate') { $rate = [int]$request.rate }
if ($request.PSObject.Properties.Name -contains 'prosody') { $prosody = [bool]$request.prosody }
if ($rate -lt -10 -or $rate -gt 10) { throw '语速必须在-10至10之间' }
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'zh-CN' -and
        (-not $voiceName -or $_.VoiceInfo.Name -eq $voiceName)
    } | Select-Object -First 1
    if (-not $voice) {
        # 瑶瑶等OneCore音色通过Windows现代接口使用，不修改系统注册表。
        & (Join-Path $PSScriptRoot 'tts-winrt.ps1') -Text ([string]$request.text) `
            -VoiceName $voiceName -Rate $rate -Prosody $prosody -OutputFile $OutputFile
        return
    }
    $speaker.SelectVoice($voice.VoiceInfo.Name)
    $speaker.Rate = $rate
    $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(
        16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono)
    $speaker.SetOutputToWaveFile($OutputFile, $format)
    if (-not $prosody) {
        $speaker.Speak([string]$request.text)
    } else {
        $prompt = [System.Speech.Synthesis.PromptBuilder]::new(
            [System.Globalization.CultureInfo]::GetCultureInfo('zh-CN'))
        # 文字通过AppendText加入，不把模型正文作为SSML或PowerShell执行。
        $parts = [regex]::Matches([string]$request.text, '[^，,。！？!?；;：:\r\n]+[，,。！？!?；;：:]*|[\r\n]+')
        for ($i = 0; $i -lt $parts.Count; $i++) {
            $part = $parts[$i].Value
            if ($part.Trim()) { $prompt.AppendText($part) }
            if ($i -lt $parts.Count - 1) {
                $pause = 0
                if ($part -match '[。！？!?\r\n]$') { $pause = 220 }
                elseif ($part -match '[；;：:]$') { $pause = 160 }
                elseif ($part -match '[，,]$') { $pause = 100 }
                if ($pause) { $prompt.AppendBreak([TimeSpan]::FromMilliseconds($pause)) }
            }
        }
        $speaker.Speak($prompt)
    }
    $speaker.SetOutputToNull()
} finally { $speaker.Dispose() }
