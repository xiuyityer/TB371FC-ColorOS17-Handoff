param(
    [switch]$Check,
    [switch]$Resume,
    [switch]$Restart,
    [string]$Serial,
    [string]$StateDir = 'flash-state'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (!$Check) {
    Write-Host '此操作将清除平板的所有用户数据，包括应用、照片和本地文件。'
    $answer = Read-Host '输入 WIPE 同意并开始刷机，其他输入取消 [默认取消]'
    if ($answer -cne 'WIPE') {
        Write-Host '已取消，未清除数据或刷入镜像。'
        exit 0
    }
}

function Invoke-NativeFastboot([string[]]$Arguments) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = Join-Path $PSScriptRoot 'tools\windows\fastboot.exe'
    $info.WorkingDirectory = $PSScriptRoot
    $info.Arguments = ($Arguments | ForEach-Object {
        if ($_.Contains('"')) { throw 'Fastboot 参数含引号。' }
        '"' + ($_ -replace '(\\+)$', '$1$1') + '"'
    }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = [System.Diagnostics.Process]::Start($info)
    try {
        $outTask = $process.StandardOutput.ReadToEndAsync()
        $errTask = $process.StandardError.ReadToEndAsync()
        if (!$process.WaitForExit(120000)) {
            $process.Kill()
            throw "Fastboot 命令超时：$($Arguments -join ' ')"
        }
        $output = $outTask.GetAwaiter().GetResult() + $errTask.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw $output.TrimEnd() }
        return $output
    } finally {
        $process.Dispose()
    }
}

function Invoke-DeviceFastboot([string[]]$Arguments) {
    Add-Content -LiteralPath $logPath -Value "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $($Arguments -join ' ')"
    try {
        $output = Invoke-NativeFastboot (@('-s', $Serial) + $Arguments)
        Add-Content -LiteralPath $logPath -Value $output
        return $output
    } catch {
        Add-Content -LiteralPath $logPath -Value $_.Exception.Message
        throw
    }
}

function Read-DeviceVar([string]$Name) {
    $output = Invoke-DeviceFastboot @('getvar', $Name)
    $match = [regex]::Match($output, '(?m)^\s*(?:\(bootloader\)\s*)?' + [regex]::Escape($Name) + ':\s*(\S+)')
    if (!$match.Success) { throw "设备未返回 $Name。" }
    return $match.Groups[1].Value
}

function Read-Size([string]$Text) {
    if ($Text.StartsWith('0x', [StringComparison]::OrdinalIgnoreCase)) {
        return [Convert]::ToInt64($Text.Substring(2), 16)
    }
    return [long]$Text
}

function Save-Progress([int]$Step) {
    $temporary = "$checkpoint.tmp"
    Set-Content -LiteralPath $temporary -Value "$identity $Step" -Encoding Ascii
    Move-Item -LiteralPath $temporary -Destination $checkpoint -Force
}

try {
    if ($Resume -and $Restart) { throw '-Resume 和 -Restart 请选择其一。' }
    Write-Host '正在校验镜像和刷写清单…'
    foreach ($line in Get-Content -LiteralPath 'payload.sha256') {
        $match = [regex]::Match($line, '^([a-f0-9]{64})  ((?:super/|apps/)?[A-Za-z0-9_.-]+)$')
        if (!$match.Success) { throw '校验清单格式有误。' }
        $expected = $match.Groups[1].Value
        $entry = $match.Groups[2].Value
        if ((Get-FileHash -LiteralPath $entry -Algorithm SHA256).Hash -ne $expected) {
            throw "校验失败，请重新解压刷机包：$entry"
        }
    }
    if ($Check) {
        Write-Host '离线校验通过。'
        exit 0
    }
    $devices = @([regex]::Matches((Invoke-NativeFastboot @('devices')), '(?m)^(\S+)\s+fastboot\s*$') |
        ForEach-Object { $_.Groups[1].Value })
    if (!$Serial) {
        if ($devices.Count -ne 1) {
            throw '请连接一台处在 Bootloader Fastboot 的平板，或用 -Serial 指定设备。'
        }
        $Serial = $devices[0]
    }
    if ($Serial -cnotmatch '^[A-Za-z0-9_.-]+$' -or [Array]::IndexOf($devices, $Serial) -lt 0) {
        throw '指定设备不在 Fastboot。'
    }
    $null = New-Item -ItemType Directory -Path $StateDir -Force
    $checkpoint = Join-Path $StateDir "$Serial.progress"
    $logPath = Join-Path $StateDir "$Serial.log"

    if ((Read-DeviceVar 'product') -cne 'spinel') { throw '仅支持联想 TB371FC（spinel）。' }
    if ((Read-DeviceVar 'unlocked') -cne 'yes') { throw '设备的 Bootloader 尚未解锁。' }
    if ((Read-DeviceVar 'is-userspace') -cne 'no') { throw '请进入 Bootloader Fastboot。' }
    $sizes = @{super = 12884901888L; boot_a = 100663296L; recovery_a = 104857600L}
    foreach ($name in $sizes.Keys) {
        if ((Read-Size (Read-DeviceVar "partition-size:$name")) -ne $sizes[$name]) {
            throw "分区尺寸不匹配：$name"
        }
    }
    foreach ($name in @('userdata', 'metadata')) {
        if ((Read-Size (Read-DeviceVar "partition-size:$name")) -le 0) {
            throw "没有预期的数据分区：$name"
        }
    }
    if ((Read-Size (Read-DeviceVar 'max-download-size')) -lt 100663296) {
        throw 'Fastboot 下载上限低于镜像尺寸。'
    }
    if (@('a', 'b') -notcontains (Read-DeviceVar 'current-slot')) { throw '无法识别当前槽位。' }

    $identity = (Get-FileHash -LiteralPath 'payload.sha256' -Algorithm SHA256).Hash.ToLowerInvariant()
    $plan = @(Get-Content -LiteralPath 'flash-plan.tsv')
    $next = 0
    if ($Resume) {
        $state = Get-Content -LiteralPath $checkpoint -Raw
        $match = [regex]::Match($state, '^([a-f0-9]{64}) ([0-9]+)\s*$')
        if (!$match.Success -or $match.Groups[1].Value -cne $identity) {
            throw '无效的断点或断点属于其他刷机包。'
        }
        $next = [int]$match.Groups[2].Value
        if ($next -gt $plan.Count) { throw '无效的断点。' }
        Write-Host "从已确认的第 $next 步继续。"
    } else {
        if ((Test-Path -LiteralPath $checkpoint) -and !$Restart) {
            throw '已有刷机记录。使用 -Resume 续刷，或 -Restart 从头开始。'
        }
        Save-Progress 0
    }

    for ($index = $next; $index -lt $plan.Count; $index++) {
        $fields = $plan[$index] -split "`t"
        $action, $partition, $image = $fields
        switch -Regex ("${action}:$partition") {
            '^flash:(recovery_a|super|boot_a)$' {
                $null = Invoke-DeviceFastboot @('flash', $partition, (Join-Path $PSScriptRoot $image))
            }
            '^erase:(userdata|metadata)$' {
                $null = Invoke-DeviceFastboot @('erase', $partition)
            }
            '^set_active:a$' {
                $null = Invoke-DeviceFastboot @('set_active', 'a')
            }
            default { throw '刷写清单含未知操作。' }
        }
        $step = $index + 1
        Save-Progress $step
        if ($partition -ne 'super' -or $step % 20 -eq 0) {
            Write-Host "完成 $step/$($plan.Count)  $action $partition"
        }
    }
    if ((Read-DeviceVar 'current-slot') -cne 'a') { throw 'A 槽切换未确认。' }
    Write-Host (Invoke-DeviceFastboot @('reboot'))
    Write-Host '镜像刷入和用户数据清除已完成，请在平板上完成首次设置。'
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
