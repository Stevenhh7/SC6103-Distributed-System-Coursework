# B 的单例/模式验收驱动：每次启动自己的 Java 进程，结束只停止自己启动的进程。
param(
    [ValidateSet('baseline', 'request_loss_reserve', 'reply_loss_reserve', 'reply_loss_increase',
                 'reply_loss_set', 'all_request_loss', 'all_reply_loss', 'monitor')]
    [string]$Case = 'baseline',
    [ValidateSet('alo', 'amo')][string]$Semantics = 'amo',
    [ValidateRange(1, 65535)][int]$Port = 6789,
    [ValidateRange(1, 65535)][int]$ProxyPort = 6790,
    [string]$Python = 'python',
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$bRunRoot = Split-Path -Parent $PSScriptRoot
$bClasses = Join-Path $bRunRoot 'server\build\classes'
$bSession = [guid]::NewGuid().ToString()
$bClientCase = if ($Case -in @('all_request_loss', 'all_reply_loss')) { 'reply_loss_reserve' } else { $Case }
$bClientPort = if ($Case -in @('all_request_loss', 'all_reply_loss')) { $ProxyPort } else { $Port }
$bUnknownExpected = $Case -in @('all_request_loss', 'all_reply_loss')
$bExpectedSeats = 10
$bExpectedFare = 100
switch ($Case) {
    'baseline' { $bExpectedSeats = 9; $bExpectedFare = 140 }
    'request_loss_reserve' { $bExpectedSeats = 9 }
    'reply_loss_reserve' { $bExpectedSeats = if ($Semantics -eq 'alo') { 8 } else { 9 } }
    'reply_loss_increase' { $bExpectedFare = if ($Semantics -eq 'alo') { 140 } else { 120 } }
    'reply_loss_set' { $bExpectedFare = 120 }
    'all_reply_loss' { $bExpectedSeats = if ($Semantics -eq 'alo') { 5 } else { 9 } }
}
$bTarget = if ($Case -eq 'baseline') { 'reserve:3 set:4 increase:5' } elseif ($Case -eq 'monitor') { 'none (monitor:2)' } else { "${bSession}:2" }
Write-Output "Case=$Case; mode=$Semantics; seed=1001 seats=10 fare=100; write target=$bTarget"
Write-Output "Expected final seats=$bExpectedSeats fare=$bExpectedFare; unknown=$bUnknownExpected"
if ($DryRun) {
    Write-Output 'DRY RUN: no processes, sockets or result records were created.'
    return
}
if ($Port -eq $ProxyPort -and $bUnknownExpected) { throw 'ProxyPort must differ from server Port.' }

# 在当前 A 占位实现下明确拒绝真实实验，不制造通过记录。
foreach ($bAFile in @('BinaryProtocolCodec.java', 'UdpTransport.java', 'UdpServer.java',
                       'RequestDispatcher.java', 'InMemoryRequestHistory.java', 'LossSimulator.java')) {
    $bAPath = Join-Path $bRunRoot "server\src\flight\$bAFile"
    if (Select-String -LiteralPath $bAPath -Pattern 'throw new UnsupportedOperationException' -Quiet) {
        throw "A implementation pending in $bAFile. Run server/test-b.ps1 for B independent tests; this network case was NOT executed."
    }
}

$bStamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$bEvidence = Join-Path $bRunRoot "evidence\b\runs\${bStamp}_${Case}_${Semantics}"
New-Item -ItemType Directory -Path $bEvidence -Force | Out-Null
$bClientLog = Join-Path $bEvidence 'client.jsonl'
$bServer = $null
$bProxy = $null
$bFailed = $false
$bRow = [ordered]@{
    case = $Case; mode = $Semantics; session = $bSession; flight_id = 1001
    initial_seats = ''; final_seats = ''; initial_fare = ''; final_fare = ''
    mutation_attempts = ''; client_unknown = ''; business_executions = ''; cache_hits = ''
    result = 'FAILED_OR_INCOMPLETE'; evidence = $bEvidence
    notes = 'Actual executions/cache hits require A server logs; never inferred from expectations.'
}
Push-Location $bRunRoot
try {
    & (Join-Path $bRunRoot 'server\build.ps1')
    $bJava = (Get-Command java -ErrorAction Stop).Source
    $bPythonPath = (Get-Command $Python -ErrorAction Stop).Source
    $bPorts = @([string]$Port)
    if ($bUnknownExpected) { $bPorts += [string]$ProxyPort }
    & $bPythonPath -X utf8 -m experiments.runtime_check ports @bPorts
    if ($LASTEXITCODE -ne 0) { throw 'Experiment port is occupied; no server/proxy was started.' }
    $bServerArgs = @('-cp', ('"{0}"' -f $bClasses), 'flight.ServerMain', '--bind', '127.0.0.1',
                     '--port', [string]$Port, '--semantics', $Semantics)
    if ($Case -in @('reply_loss_reserve', 'reply_loss_increase', 'reply_loss_set')) {
        $bServerArgs += @('--drop-first-reply', "${bSession}:2")
    }
    $bServer = Start-Process -FilePath $bJava -ArgumentList $bServerArgs -WorkingDirectory $bRunRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $bEvidence 'server.stdout.txt') -RedirectStandardError (Join-Path $bEvidence 'server.stderr.txt')
    $bReady = @(& $bPythonPath -X utf8 -m experiments.runtime_check ready --port $Port --mode $Semantics)
    $bReadyExit = $LASTEXITCODE
    $bReady | Set-Content -LiteralPath (Join-Path $bEvidence 'readiness.jsonl') -Encoding UTF8
    $bServer.Refresh()
    if ($bServer.HasExited -or $bReadyExit -ne 0) { throw 'Owned Java server is not ready; inspect readiness/server logs.' }
    if ($bUnknownExpected) {
        $bDrop = if ($Case -eq 'all_request_loss') { 'requests' } else { 'replies' }
        $bProxyArgs = @('-X', 'utf8', '-m', 'experiments.udp_loss_proxy', '--listen-port', [string]$ProxyPort,
                        '--server-port', [string]$Port, '--session-id', $bSession, '--request-id', '2', '--drop', $bDrop)
        $bProxy = Start-Process -FilePath $bPythonPath -ArgumentList $bProxyArgs -WorkingDirectory $bRunRoot -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $bEvidence 'proxy.jsonl') -RedirectStandardError (Join-Path $bEvidence 'proxy.stderr.txt')
        # 就绪探测不能经代理发送：代理只接受一个客户端端点，会把探测端点当正式客户端。
        $bProxyReady = $false
        $bReadyWatch = [System.Diagnostics.Stopwatch]::StartNew()
        while ($bReadyWatch.ElapsedMilliseconds -lt 5000) {
            $bProxy.Refresh()
            if ($bProxy.HasExited) { throw 'Loss proxy exited before readiness; inspect proxy.stderr.txt.' }
            if (Select-String -LiteralPath (Join-Path $bEvidence 'proxy.jsonl') -Pattern '"event": "PROXY_READY"' -Quiet) {
                $bProxyReady = $true
                break
            }
            Start-Sleep -Milliseconds 50
        }
        if (-not $bProxyReady) { throw 'Loss proxy did not report readiness within 5 seconds.' }
    }
    $bServer.Refresh()
    if ($bServer.HasExited) { throw 'Java server exited before the case; inspect server.stderr.txt.' }
    if ($bProxy) {
        $bProxy.Refresh()
        if ($bProxy.HasExited) { throw 'Loss proxy exited before the case; inspect proxy.stderr.txt.' }
    }
    $bClientArgs = @('-X', 'utf8', '-m', 'client', '--server', '127.0.0.1', '--port', [string]$bClientPort,
        '--semantics', $Semantics, '--session-id', $bSession, '--case', $bClientCase,
        '--flight-id', '1001', '--source', 'Singapore', '--destination', 'Beijing',
        '--quantity', '1', '--new-price', '120', '--delta', '20', '--monitor-seconds', '2',
        '--timeout-ms', '1000', '--max-attempts', '5', '--log-file', $bClientLog)
    $bSavedErrorPreference = $ErrorActionPreference
    try {
        # 预期“结果未知”会由 C 返回 1，仍保存 stdout/stderr 并分析真实终态。
        $ErrorActionPreference = 'Continue'
        $bConsole = @(& $bPythonPath @bClientArgs 2>&1)
        $bClientExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $bSavedErrorPreference }
    $bConsole | ForEach-Object { [string]$_ } | Set-Content -LiteralPath (Join-Path $bEvidence 'client.console.txt') -Encoding UTF8
    # 在读取代理日志前结束自己创建的进程，保证最终输出完整。
    foreach ($bOwnedProcess in @($bProxy, $bServer)) {
        if ($null -ne $bOwnedProcess) {
            $bOwnedProcess.Refresh()
            if (-not $bOwnedProcess.HasExited) { Stop-Process -Id $bOwnedProcess.Id -ErrorAction Stop }
            if (-not $bOwnedProcess.WaitForExit(5000)) { throw 'Owned process did not finish within 5 seconds.' }
        }
    }
    $bAnalysisPath = Join-Path $bEvidence 'analysis.json'
    $bAnalysisArgs = @('-X', 'utf8', '-m', 'experiments.analyze_results', '--client-log', $bClientLog,
                      '--case', $Case, '--mode', $Semantics, '--session', $bSession,
                      '--client-exit', [string]$bClientExit, '--output', $bAnalysisPath)
    if ($bProxy) { $bAnalysisArgs += @('--proxy-log', (Join-Path $bEvidence 'proxy.jsonl')) }
    & $bPythonPath @bAnalysisArgs
    $bAnalysisExit = $LASTEXITCODE
    if (Test-Path -LiteralPath $bAnalysisPath) {
        $bAnalysis = Get-Content -Raw -LiteralPath $bAnalysisPath -Encoding UTF8 | ConvertFrom-Json
        foreach ($bProperty in $bAnalysis.PSObject.Properties) { $bRow[$bProperty.Name] = $bProperty.Value }
    }
    if ($bAnalysisExit -ne 0) { throw "Evidence validation failed: $($bRow.notes)" }
    Write-Output "State verified; evidence=$bEvidence. Review A business execution/cache logs before final acceptance."
} catch {
    $bFailed = $true
    $bRow.result = 'FAILED_OR_INCOMPLETE'
    $bRow.notes = [string]$_.Exception.Message
    throw
} finally {
    $bFinalizationErrors = [System.Collections.Generic.List[string]]::new()
    foreach ($bOwnedProcess in @($bProxy, $bServer)) {
        if ($null -ne $bOwnedProcess) {
            try {
                $bOwnedProcess.Refresh()
                if (-not $bOwnedProcess.HasExited) { Stop-Process -Id $bOwnedProcess.Id -ErrorAction Stop }
            } catch { $bFinalizationErrors.Add("Process cleanup: $($_.Exception.Message)") }
        }
    }
    try {
        if ($bFinalizationErrors.Count) { $bRow.result = 'FAILED_OR_INCOMPLETE' }
        [pscustomobject]$bRow | Export-Csv -LiteralPath (Join-Path $bEvidence 'result.csv') -NoTypeInformation -Encoding UTF8
        [pscustomobject]$bRow | Export-Csv -LiteralPath (Join-Path $bRunRoot 'experiments\results.csv') -Append -NoTypeInformation -Encoding UTF8
    } catch { $bFinalizationErrors.Add("Result write: $($_.Exception.Message)") }
    finally { Pop-Location }
    if ($bFinalizationErrors.Count) {
        $bFinalizationErrors | ForEach-Object { Write-Warning $_ }
        if (-not $bFailed) { throw 'Experiment finalization failed; preserve per-run logs/results.' }
    }
}
