# B 独立验证入口；只编译生产源码与 B 测试，不修改 A 的 build.ps1。
param([string]$EvidenceFile = '')
$ErrorActionPreference = 'Stop'
$bSourceRoot = Join-Path $PSScriptRoot 'src'
$bTestRoot = Join-Path $PSScriptRoot 'test\flight\b'
$bClasses = Join-Path $PSScriptRoot 'build\b-test-classes'
$bSources = @(
    Get-ChildItem -LiteralPath $bSourceRoot -Filter '*.java' -File -Recurse | ForEach-Object { $_.FullName }
    Get-ChildItem -LiteralPath $bTestRoot -Filter '*.java' -File -Recurse | ForEach-Object { $_.FullName }
)
New-Item -ItemType Directory -Path $bClasses -Force | Out-Null
if ($EvidenceFile) {
    $bEvidenceParent = Split-Path -Parent $EvidenceFile
    if ($bEvidenceParent) { New-Item -ItemType Directory -Path $bEvidenceParent -Force | Out-Null }
}
& javac --release 17 -encoding UTF-8 -d $bClasses @bSources
if ($LASTEXITCODE -ne 0) { throw 'B test compilation failed.' }
$bOutput = [System.Collections.Generic.List[string]]::new()
$bOutput.Add('B tests: compilation target Java 17; deterministic in-process tests, not UDP integration')
foreach ($bSuite in @('flight.BusinessSelfTest', 'flight.MonitorSelfTest')) {
    $bLines = @(& java -cp $bClasses $bSuite 2>&1)
    $bExitCode = $LASTEXITCODE
    foreach ($bLine in $bLines) { $bOutput.Add([string]$bLine); Write-Output ([string]$bLine) }
    if ($bExitCode -ne 0) {
        if ($EvidenceFile) { $bOutput | Set-Content -LiteralPath $EvidenceFile -Encoding UTF8 }
        throw "B suite failed: $bSuite"
    }
}
if ($EvidenceFile) {
    $bOutput | Set-Content -LiteralPath $EvidenceFile -Encoding UTF8
}
Write-Output 'B module validation passed. A/C network integration remains a separate gate.'
