param([switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) {
    throw '请先在主项目创建 .venv 并安装 backend/requirements-ocr.txt，详见 backend/docs/certificate-ocr.md。'
}
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $backendRoot 'instance/certificate-local.db') -replace '\\', '/')
& $pythonExe -B (Join-Path $backendRoot 'tools/prepare_local.py')
if ($LASTEXITCODE -ne 0) { throw '本地数据库准备失败。' }
& $pythonExe -B (Join-Path $backendRoot 'tools/setup_certificate_models.py')
if ($LASTEXITCODE -ne 0) { throw 'OCR 模型准备失败。' }
if ($PrepareOnly) { return }
$logRoot = Join-Path $backendRoot 'logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$webProcess = $null
$workerProcess = $null
try {
    $webProcess = Start-Process -FilePath $pythonExe -ArgumentList '-B', 'app.py' -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'local-web.out.log') -RedirectStandardError (Join-Path $logRoot 'local-web.err.log')
    $workerProcess = Start-Process -FilePath $pythonExe -ArgumentList '-B', 'recognition_worker.py' -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot 'local-worker.out.log') -RedirectStandardError (Join-Path $logRoot 'local-worker.err.log')
    Write-Host '后端和识别进程已启动。打开前端输出中的地址；按 Ctrl+C 退出时会结束本次启动的后端进程。'
    Push-Location (Join-Path $projectRoot 'frontend')
    try { npm run dev -- --host 127.0.0.1 }
    finally { Pop-Location }
}
finally {
    foreach ($ownedProcess in @($webProcess, $workerProcess)) {
        if ($null -ne $ownedProcess -and !$ownedProcess.HasExited) { $ownedProcess.Kill(); $ownedProcess.WaitForExit() }
    }
}
