# 仅配置本任务的USB网卡，不修改其他接口、DNS、代理或防火墙。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$resultPath = Join-Path $projectRoot 'records/RNDIS传输/电脑网卡设置.json'
try {
    $devices = @(Get-CimInstance Win32_NetworkAdapter | Where-Object {
        $_.PNPDeviceID -like 'USB\VID_0525&PID_A4A2&MI_00\*' -and $_.NetEnabled
    })
    if ($devices.Count -ne 1) { throw '没有找到唯一在线的本任务USB网卡，停止配置' }
    $usbDevice = $devices[0]
    if (($usbDevice.MACAddress -replace '[:-]', '') -ne '021130000001') {
        throw 'USB网卡MAC地址与本任务不符，停止配置'
    }
    $interfaceIndex = [int]$usbDevice.InterfaceIndex
    $originalDhcp = (Get-NetIPInterface -InterfaceIndex $interfaceIndex -AddressFamily IPv4).Dhcp.ToString()
    $existing = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq '192.168.113.1' })
    if ($existing.Count -and $existing[0].InterfaceIndex -ne $interfaceIndex) {
        throw '目标地址已被其他网卡使用，停止配置'
    }
    if (-not $existing.Count) {
        New-NetIPAddress -InterfaceIndex $interfaceIndex -IPAddress '192.168.113.1' `
            -PrefixLength 30 -AddressFamily IPv4 -PolicyStore ActiveStore | Out-Null
    }
    $result = @{ '成功' = $true; '接口索引' = $interfaceIndex;
        '地址' = '192.168.113.1/30'; '原DHCP状态' = $originalDhcp;
        '作用范围' = '仅本次运行的USB网卡；无默认网关、无DNS变更、无防火墙变更' }
    $result | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    @{ '成功' = $false; '错误' = $_.Exception.Message } |
        ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    exit 1
}
