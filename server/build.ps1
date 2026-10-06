# [A-00] Java 17 本地构建脚本；无 Maven/Gradle/网络依赖。
# 使用脚本所在目录定位源码，允许仓库路径包含空格。
$ErrorActionPreference = 'Stop'
$taskSourceDirectory = Join-Path $PSScriptRoot 'src'
$taskOutputDirectory = Join-Path $PSScriptRoot 'build\classes'
$taskSources = @(Get-ChildItem -LiteralPath $taskSourceDirectory -Filter '*.java' -File -Recurse | ForEach-Object { $_.FullName })
if ($taskSources.Count -eq 0) { throw 'No Java source files were found.' }
New-Item -ItemType Directory -Force -Path $taskOutputDirectory | Out-Null
& javac --release 17 -encoding UTF-8 -d $taskOutputDirectory @taskSources
if ($LASTEXITCODE -ne 0) { throw 'Java compilation failed.' }
Write-Output ("Compiled {0} Java scaffold files into {1}" -f $taskSources.Count, $taskOutputDirectory)
