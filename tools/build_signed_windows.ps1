# Developer-only build, not authorization to distribute. Never disable Smart App Control.
param([string]$TrustedCertificateThumbprint, [switch]$BuildOnly)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
if (!(Test-Path "tools/windows_fictional_gui.py")) { throw "Run from repository root" }
& py -3.11 -m PyInstaller --clean --noconfirm --windowed --onedir --paths . --name MyTravelingLawyer-Practice tools/windows_fictional_gui.py
if ($LASTEXITCODE -ne 0) { throw "Windows EXE build failed" }
$root="dist/MyTravelingLawyer-Practice"
if (!(Test-Path "$root/MyTravelingLawyer-Practice.exe")) { throw "EXE missing" }
if ($BuildOnly) { Write-Host "UNSIGNED; do NOT give this to an evaluator."; exit 0 }
if ([string]::IsNullOrWhiteSpace($TrustedCertificateThumbprint)) { throw "Approved trusted signing certificate thumbprint required; NOT SIGNED" }
$cert=Get-ChildItem "Cert:\CurrentUser\My","Cert:\LocalMachine\My" |
  Where-Object { $_.Thumbprint -eq $TrustedCertificateThumbprint -and $_.HasPrivateKey } |
  Select-Object -First 1
if ($null -eq $cert -or !$cert.Verify()) { throw "Trusted code-signing certificate NOT available; nothing signed" }
$tool=Get-Command signtool.exe -ErrorAction SilentlyContinue
if (!$tool) { $tool=Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1 }
if (!$tool) { throw "Windows SDK SignTool is required" }
$path=if ($tool.Source) { $tool.Source } else { $tool.FullName }
$pe=@(Get-ChildItem $root -Recurse -File | Where-Object { $_.Extension -in @(".exe",".dll",".pyd") })
if (!$pe.Count) { throw "No PE binaries" }
foreach ($file in $pe) {
  if ((Get-AuthenticodeSignature $file.FullName).Status -ne "Valid") {
    & $path sign /sha1 $cert.Thumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $($file.Name)" }
  }
}
foreach ($file in $pe) {
  & $path verify /pa $file.FullName
  if ($LASTEXITCODE -ne 0) { throw "Untrusted code inside package: $($file.Name)" }
}
Write-Host "LOCAL SIGNATURE VERIFIED. Smart App Control execution still needs separate real Windows acceptance."
