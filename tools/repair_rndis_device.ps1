# 由配套Python入口设置ProjectRoot；仅修复本任务的RNDIS设备，不删除驱动。
$ErrorActionPreference = 'Stop'
$resultPath = Join-Path $ProjectRoot 'records/RNDIS传输/设备恢复结果.json'
try {
    $devices = @(Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.PNPDeviceID -like 'USB\VID_0525&PID_A4A2&MI_00\*'
    })
    if ($devices.Count -ne 1) { throw '没有找到唯一的本任务RNDIS设备，停止' }
    $device = $devices[0]
    $before = [int]$device.ConfigManagerErrorCode
    if ($before -ne 0) {
        & "$env:windir/System32/pnputil.exe" /restart-device $device.PNPDeviceID | Out-Null
        if ($LASTEXITCODE -ne 0) { throw '指定RNDIS设备重启失败；没有卸载任何驱动' }
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            Start-Sleep -Milliseconds 500
            $current = Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $device.PNPDeviceID
            if ($current.ConfigManagerErrorCode -eq 0) { break }
        }
        if ($current.ConfigManagerErrorCode -ne 0) {
            # 用户已单独授权重新识别该设备实例；不删除驱动包或父USB设备。
            & "$env:windir/System32/pnputil.exe" /remove-device $device.PNPDeviceID | Out-Null
            if ($LASTEXITCODE -ne 0) { throw '指定RNDIS子设备实例移除失败，停止' }
            & "$env:windir/System32/pnputil.exe" /scan-devices | Out-Null
            if ($LASTEXITCODE -ne 0) { throw '重新扫描设备失败；系统驱动包仍保留' }
            for ($attempt = 0; $attempt -lt 30; $attempt++) {
                Start-Sleep -Milliseconds 500
                $current = Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $device.PNPDeviceID
                if ($current -and $current.ConfigManagerErrorCode -eq 0) { break }
            }
            if (-not $current -or $current.ConfigManagerErrorCode -ne 0) {
                throw '重新识别后RNDIS仍未正常启动，停止配置地址；未删除驱动包'
            }
        }
    }
    $adapters = @(Get-CimInstance Win32_NetworkAdapter | Where-Object {
        $_.PNPDeviceID -eq $device.PNPDeviceID -and $_.NetEnabled
    })
    if ($adapters.Count -ne 1) { throw '驱动尚未生成唯一在线网卡，停止' }
    $adapter = $adapters[0]
    if (($adapter.MACAddress -replace '[:-]', '') -ne '021130000001') {
        throw '网卡MAC不属于本任务，停止'
    }
    $index = [int]$adapter.InterfaceIndex
    $existing = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq '192.168.113.1')
    if ($existing.Count -and $existing[0].InterfaceIndex -ne $index) { throw '地址被其他网卡占用，停止' }
    if (-not $existing.Count) {
        New-NetIPAddress -InterfaceIndex $index -IPAddress '192.168.113.1' -PrefixLength 30 `
            -AddressFamily IPv4 -PolicyStore ActiveStore | Out-Null
    }
    @{ '成功' = $true; '原设备错误码' = $before; '接口索引' = $index;
        '地址' = '192.168.113.1/30'; '范围' = '仅本任务RNDIS设备；未改Wi-Fi、代理、网关、DNS或防火墙' } |
        ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    @{ '成功' = $false; '错误' = $_.Exception.Message } |
        ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    exit 1
}
