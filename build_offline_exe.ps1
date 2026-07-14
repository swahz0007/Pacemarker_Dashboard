$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FinalPackageDir = Join-Path $ProjectRoot "PacemakerDashboard_offline"
$StagingRoot = Join-Path $ProjectRoot ".offline_build"
$DistRoot = Join-Path $StagingRoot "dist"
$BuildRoot = Join-Path $StagingRoot "work"

function Assert-ProjectChildPath {
  param([Parameter(Mandatory = $true)][string]$Path)

  $projectPrefix = [System.IO.Path]::GetFullPath($ProjectRoot) + [System.IO.Path]::DirectorySeparatorChar
  $fullPath = [System.IO.Path]::GetFullPath($Path)
  if (-not $fullPath.StartsWith($projectPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "拒绝操作项目目录之外的路径：$fullPath"
  }
}

Assert-ProjectChildPath -Path $FinalPackageDir
Assert-ProjectChildPath -Path $StagingRoot

if (Test-Path -LiteralPath $StagingRoot) {
  Remove-Item -LiteralPath $StagingRoot -Recurse -Force
}

Write-Host "[1/3] 检查并生成本地前端运行资源..."
npm run build:identity
if ($LASTEXITCODE -ne 0) {
  throw "前端资源构建失败，退出码：$LASTEXITCODE"
}

Write-Host "[2/3] 使用 PyInstaller 构建目录版 EXE..."
python -m PyInstaller `
  --noconfirm `
  --clean `
  --distpath $DistRoot `
  --workpath $BuildRoot `
  (Join-Path $ProjectRoot "pacemaker_dashboard.spec")
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller 构建失败，退出码：$LASTEXITCODE"
}

Write-Host "[3/3] 写入说明并发布根目录离线包..."
$StagedPackageDir = Join-Path $DistRoot "PacemakerDashboard"
if (-not (Test-Path -LiteralPath $StagedPackageDir)) {
  throw "PyInstaller 输出目录不存在：$StagedPackageDir"
}

$Readme = @"
Pacemaker Dashboard 离线运行包

首次运行 PacemakerDashboard.exe 时选择科室程控报告目录。
程序只读扫描报告目录，派生数据默认写入：
%LOCALAPPDATA%\PacemakerDashboard\runtime_data

命令行选项：
PacemakerDashboard.exe --configure
PacemakerDashboard.exe --report-dir "\\NAS\科室\程控报告" --no-open
PacemakerDashboard.exe --full

本离线包不包含真实患者数据，也不包含项目源代码。
"@
Set-Content -LiteralPath (Join-Path $StagedPackageDir "使用说明.txt") -Value $Readme -Encoding UTF8

if (Test-Path -LiteralPath $FinalPackageDir) {
  Remove-Item -LiteralPath $FinalPackageDir -Recurse -Force
}
Move-Item -LiteralPath $StagedPackageDir -Destination $FinalPackageDir

if (Test-Path -LiteralPath $StagingRoot) {
  Remove-Item -LiteralPath $StagingRoot -Recurse -Force
}

Write-Host "构建完成：$FinalPackageDir"
Write-Host "交付时直接复制整个 PacemakerDashboard_offline 文件夹；不再生成 ZIP。"
