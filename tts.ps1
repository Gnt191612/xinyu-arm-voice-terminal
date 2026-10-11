param([Parameter(Mandatory=$true)][string]$RequestFile,
      [Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$request = Get-Content -LiteralPath $RequestFile -Raw -Encoding UTF8 | ConvertFrom-Json
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'zh-CN'
    } | Select-Object -First 1
    if (-not $voice) { throw 'Windows缺少简体中文语音，请安装中文语音包' }
    $speaker.SelectVoice($voice.VoiceInfo.Name)
    $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(
        16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono)
    $speaker.SetOutputToWaveFile($OutputFile, $format)
    $speaker.Speak([string]$request.text)
} finally { $speaker.Dispose() }
