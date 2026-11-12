# Exact-SHA, read-only inspection of a new isolated GitHub Windows runner.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:GITHUB_REF -ne 'refs/heads/diesel/mtl-windows-error-probe-20261112') { throw 'BRANCH_DENIED' }
if ($env:GITHUB_EVENT_NAME -ne 'push') { throw 'EVENT_DENIED' }
if ((git rev-parse HEAD).Trim() -ne $env:GITHUB_SHA) { throw 'EXACT_SHA_DENIED' }
$exe = (Resolve-Path 'dist/MyTravelingLawyer-Practice/MyTravelingLawyer-Practice.exe').Path
$toc = Get-Content 'build/MyTravelingLawyer-Practice/Analysis-00.toc' -Raw
if ($toc -notmatch 'src.local_operator_gui') { throw 'BUNDLED_GUI_MISSING' }
$signature = (Get-AuthenticodeSignature $exe).Status.ToString()
if ($signature -ne 'NotSigned') { throw 'UNEXPECTED_SIGNATURE_STATUS' }
$doc = [ordered]@{
  git_sha=$env:GITHUB_SHA
  exe_sha256=(Get-FileHash $exe -Algorithm SHA256).Hash
  authenticode=$signature
  window_opened=$false
  clean_exit=$false
  launch_error=$null
  events=@()
  end_user_pc='NOT_ACCESSED'
  smart_app_control='NOT_PROVEN'
  production='NO_GO'
}
$since=Get-Date
$p=$null
try {
  $p=Start-Process -FilePath $exe -PassThru -ErrorAction Stop
  Start-Sleep -Seconds 5
  $p.Refresh()
  if (!$p.HasExited -and $p.MainWindowHandle -ne [IntPtr]::Zero) {
    $doc.window_opened=$true
    if ($p.CloseMainWindow()) { $doc.clean_exit=$p.WaitForExit(8000) }
  } else { $doc.launch_error='NO_LIVE_GUI_WINDOW' }
} catch {
  $doc.launch_error=$_.Exception.GetType().Name
  if ($_.Exception -is [System.ComponentModel.Win32Exception]) {
    $doc.launch_error='WIN32_'+$_.Exception.NativeErrorCode
  }
} finally {
  if ($null -ne $p) {
    $p.Refresh()
    if (!$p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  }
}
foreach ($log in @('Microsoft-Windows-CodeIntegrity/Operational','Microsoft-Windows-AppLocker/EXE and DLL','Microsoft-Windows-AppLocker/MSI and Script','Application')) {
  try {
    $events=@(Get-WinEvent -FilterHashtable @{LogName=$log;StartTime=$since} -ErrorAction Stop)
    foreach ($e in $events) {
      $message=[string]$e.Message
      if ($message.Contains('MyTravelingLawyer-Practice.exe')) {
        $m=[regex]::Match($message,'0x[0-9a-fA-F]{8}')
        $status=$null
        if ($m.Success) { $status=$m.Value.ToLowerInvariant() }
        $doc.events+=@{log=$log;id=[int]$e.Id;status=$status;exact_path=$true}
      }
    }
  } catch { Write-Output ('EVENT_LOG_UNAVAILABLE='+$log) }
}
$evidence=Join-Path $env:RUNNER_TEMP 'mtl-windows-error-evidence.json'
$doc | ConvertTo-Json -Depth 8 | Set-Content -Path $evidence -Encoding utf8
Write-Output ('EXE_SHA256='+$doc.exe_sha256)
Write-Output ('AUTHENTICODE='+$doc.authenticode)
Write-Output ('WINDOW_OPENED='+$doc.window_opened)
Write-Output ('CLEAN_EXIT='+$doc.clean_exit)
Write-Output ('LAUNCH_ERROR='+$doc.launch_error)
Write-Output ('MATCHING_EVENT_COUNT='+$doc.events.Count)
Write-Output 'SMART_APP_CONTROL=NOT_PROVEN_ON_GITHUB_RUNNER'
python -m tools.windows_error_classifier $evidence
if (!$doc.window_opened -or !$doc.clean_exit) { throw 'NATIVE_STARTUP_DENIED' }
