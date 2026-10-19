$ErrorActionPreference = 'Stop'
$toolRoot = Join-Path $PSScriptRoot '../.tools'
New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
$installer = Join-Path $toolRoot 'innosetup-6.7.3.exe'
$expectedHash = '9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732'
if (!(Test-Path -LiteralPath $installer)) {
    Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $installer
}
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'Inno Setup: o SHA-256 nao corresponde ao compilador aprovado.'
}
$destination = [IO.Path]::GetFullPath((Join-Path $toolRoot 'inno'))
if (!(Test-Path -LiteralPath (Join-Path $destination 'ISCC.exe'))) {
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', ('/DIR="' + $destination + '"'))
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'Falha ao preparar o compilador do instalador.' }
}
Write-Output (Join-Path $destination 'ISCC.exe')
