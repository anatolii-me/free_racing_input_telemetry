param(
    [string]$ArchiveName = 'ACC-Trace-Windows-Portable.zip',
    [string]$PythonPath = ''
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = if ($PythonPath) { (Resolve-Path -LiteralPath $PythonPath).Path } else { Join-Path $repo '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create .venv and install requirements.txt first.'
}

# Keep unrelated DLLs from other software on PATH out of the bundle. In
# particular, Qt must use Windows' system ICU rather than a different ICU
# distributed with another application.
$originalPath = $env:PATH
try {
    $env:PATH = (Split-Path -Parent $python) + ';' + $env:SystemRoot + '\System32;' + $env:SystemRoot
    & $python -m PyInstaller --noconfirm --clean --windowed --onedir `
        --name 'ACC-Trace' --paths $repo `
        --icon (Join-Path $PSScriptRoot 'ACC-Trace.ico') `
        --distpath (Join-Path $repo 'dist') `
        --workpath (Join-Path $repo 'build') `
        --specpath (Join-Path $repo 'build') `
        (Join-Path $PSScriptRoot 'launch.py')
    $buildExitCode = $LASTEXITCODE
} finally {
    $env:PATH = $originalPath
}
if ($buildExitCode -ne 0) {
    throw 'PyInstaller failed.'
}

$bundle = Join-Path $repo 'dist\ACC-Trace'
# Qt6Core on Windows imports the system ICU DLL. PyInstaller can incorrectly
# copy an incompatible ICU from another application on the build machine.
foreach ($dll in @('icuuc.dll', 'icudt78.dll')) {
    $foreignDll = Join-Path $bundle (Join-Path '_internal' $dll)
    if (Test-Path -LiteralPath $foreignDll) {
        Remove-Item -LiteralPath $foreignDll
    }
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'PORTABLE.txt') -Destination $bundle
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.txt') -Destination $bundle
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'LGPL-3.0.txt') -Destination $bundle
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'GPL-3.0.txt') -Destination $bundle
$archive = Join-Path $repo (Join-Path 'dist' $ArchiveName)
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive
}
Compress-Archive -LiteralPath $bundle -DestinationPath $archive -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
Set-Content -LiteralPath ($archive + '.sha256') -Value ($hash + '  ' + $ArchiveName) -Encoding ascii
Write-Output $archive
