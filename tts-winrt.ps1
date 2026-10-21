param([string]$Text, [string]$VoiceName, [int]$Rate, [bool]$Prosody, [string]$OutputFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$type = [Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]
$voice = $type::AllVoices | Where-Object { $_.DisplayName -eq $VoiceName -and $_.Language -eq 'zh-CN' } | Select-Object -First 1
if (-not $voice) { throw '未找到所选本机中文音色' }
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$stream = $reader = $file = $null
try {
    $synth.Voice = $voice
    $synth.Options.SpeakingRate = [Math]::Pow(1.1, $Rate)
    $builder = [System.Speech.Synthesis.PromptBuilder]::new(
        [System.Globalization.CultureInfo]::GetCultureInfo('zh-CN'))
    $parts = [regex]::Matches($Text, '[^，,。！？!?；;：:\r\n]+[，,。！？!?；;：:]*|[\r\n]+')
    for ($i = 0; $i -lt $parts.Count; $i++) {
        $part = $parts[$i].Value
        if ($part.Trim()) { $builder.AppendText($part) }
        if ($Prosody -and $i -lt $parts.Count - 1) {
            $pause = 0
            if ($part -match '[。！？!?\r\n]$') { $pause = 220 }
            elseif ($part -match '[；;：:]$') { $pause = 160 }
            elseif ($part -match '[，,]$') { $pause = 100 }
            if ($pause) { $builder.AppendBreak([TimeSpan]::FromMilliseconds($pause)) }
        }
    }
    $operation = $synth.SynthesizeSsmlToStreamAsync($builder.ToXml())
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $resultType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime]
    $task = $method.MakeGenericMethod($resultType).Invoke($null, @($operation))
    if (-not $task.Wait(20000)) { throw '本机音色合成超时' }
    $stream = $task.Result
    $reader = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
    $file = [IO.File]::Create($OutputFile)
    $reader.CopyTo($file)
} finally {
    if ($file) { $file.Dispose() }
    if ($reader) { $reader.Dispose() }
    if ($stream) { $stream.Dispose() }
    $synth.Dispose()
}
