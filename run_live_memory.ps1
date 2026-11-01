# Run this yourself; coding agents must not access product datapacks.
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create .venv and install requirements.txt first; see docs/memory-integration.md.'
}

Write-Host 'Use two EMPTY synthetic-data datapacks, with no concurrent application traffic.'
Write-Host 'The check writes, corrects and deletes test memories. Provider traces may remain.'
$taskConfirmation = Read-Host 'Type SYNTHETIC to continue'
if ($taskConfirmation -cne 'SYNTHETIC') { throw 'Cancelled; no Meko calls made.' }

$taskNames = @('MEKO_MCP_URL', 'MEKO_API_TOKEN', 'MEKO_BUILD_DATAPACK_ID',
               'MEKO_TEST_DATAPACK_A', 'MEKO_TEST_DATAPACK_B')
$taskPrevious = @{}
foreach ($taskName in $taskNames) {
    $taskPrevious[$taskName] = [Environment]::GetEnvironmentVariable($taskName, 'Process')
}
try {
    $env:MEKO_MCP_URL = Read-Host 'Meko HTTPS Streamable HTTP endpoint'
    $env:MEKO_BUILD_DATAPACK_ID = 'c3ea833a-a52a-49e5-9a78-23fc4276833e'
    $env:MEKO_TEST_DATAPACK_A = Read-Host 'Empty synthetic datapack A UUID'
    $env:MEKO_TEST_DATAPACK_B = Read-Host 'Empty synthetic datapack B UUID'
    $taskSecureToken = Read-Host 'Backend bearer token (hidden)' -AsSecureString
    $taskTokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecureToken)
    try {
        $env:MEKO_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskTokenPointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskTokenPointer)
        $taskSecureToken.Dispose()
    }
    & $taskPython (Join-Path $PSScriptRoot 'live_memory_check.py') --live --synthetic-datapacks
    if ($LASTEXITCODE -ne 0) { throw 'Live acceptance failed; see the status above.' }
} finally {
    foreach ($taskName in $taskNames) {
        [Environment]::SetEnvironmentVariable($taskName, $taskPrevious[$taskName], 'Process')
    }
}
