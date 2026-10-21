# 用户已明确授权：只将本任务RNDIS网卡的既定IPv4地址保存为持久配置。
$ErrorActionPreference = 'Stop'
$resultPath = Join-Path $ProjectRoot 'records/RNDIS传输/持久配置结果.json'
try {
    $adapters = @(Get-CimInstance Win32_NetworkAdapter | Where-Object {
        $_.PNPDeviceID -like 'USB\VID_0525&PID_A4A2&MI_00\*' -and $_.NetEnabled
    })
    if ($adapters.Count -ne 1) { throw '未找到唯一在线的本任务RNDIS网卡，停止' }
    $adapter = $adapters[0]
    if (($adapter.MACAddress -replace '[:-]', '') -ne '021130000001') {
        throw 'MAC地址不属于本任务，停止'
    }
    $index = [int]$adapter.InterfaceIndex
    $active = @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore ActiveStore |
        Where-Object IPAddress -eq '192.168.113.1')
    $persistent = @(Get-NetIPAddress -AddressFamily IPv4 -PolicyStore PersistentStore |
        Where-Object IPAddress -eq '192.168.113.1')
    if (@($active + $persistent | Where-Object InterfaceIndex -ne $index).Count) {
        throw '目标地址被其他接口使用，停止'
    }
    $snapshotPath = Join-Path $ProjectRoot 'records/RNDIS传输/持久配置前快照.json'
    if (-not (Test-Path -LiteralPath $snapshotPath)) {
        @{ '接口索引' = $index; '设备实例' = $adapter.PNPDeviceID; 'MAC' = $adapter.MACAddress;
            '原DHCP' = (Get-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4).Dhcp.ToString();
            '原活动地址' = @($active | Select-Object IPAddress,PrefixLength);
            '原持久地址' = @($persistent | Select-Object IPAddress,PrefixLength) } |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $snapshotPath -Encoding UTF8
    }
    if (-not $persistent.Count) {
        # 仅替换同一个临时地址；不删除其他地址，默认创建活动及持久两份配置。
        if ($active.Count) {
            Remove-NetIPAddress -InterfaceIndex $index -IPAddress '192.168.113.1' `
                -PolicyStore ActiveStore -Confirm:$false
        }
        New-NetIPAddress -InterfaceIndex $index -IPAddress '192.168.113.1' `
            -PrefixLength 30 -AddressFamily IPv4 | Out-Null
    }
    # USB重新枚举后，持久项可能仍在但活动项未自动恢复；仅补同一接口的既定地址。
    $current = @(Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -PolicyStore ActiveStore |
        Where-Object { $_.IPAddress -eq '192.168.113.1' -and $_.PrefixLength -eq 30 })
    if (-not $current.Count) {
        New-NetIPAddress -InterfaceIndex $index -IPAddress '192.168.113.1' `
            -PrefixLength 30 -AddressFamily IPv4 -PolicyStore ActiveStore | Out-Null
    }
    $saved = @(Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -PolicyStore PersistentStore |
        Where-Object { $_.IPAddress -eq '192.168.113.1' -and $_.PrefixLength -eq 30 })
    $live = @(Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -PolicyStore ActiveStore |
        Where-Object { $_.IPAddress -eq '192.168.113.1' -and $_.PrefixLength -eq 30 })
    if ($saved.Count -ne 1 -or $live.Count -ne 1) { throw '活动或持久地址核验失败' }
    @{ '成功' = $true; '接口索引' = $index; '设备实例' = $adapter.PNPDeviceID;
        '地址' = '192.168.113.1/30'; '活动配置存在' = $true; '持久配置存在' = $true;
        '范围' = '仅此RNDIS接口；未设置网关或DNS，未改Wi-Fi、Clash或防火墙' } |
        ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    @{ '成功' = $false; '错误' = $_.Exception.Message } |
        ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    exit 1
}
