$ErrorActionPreference = 'Stop'
$sshDirectory = Join-Path $env:USERPROFILE '.ssh'
$keyPath = Join-Path $sshDirectory 'id_ed25519_mhp_ecs'
$configPath = Join-Path $sshDirectory 'config'
$utf8 = [System.Text.UTF8Encoding]::new($false)
if (!(Test-Path -LiteralPath $sshDirectory)) {
    New-Item -ItemType Directory -Path $sshDirectory | Out-Null
}
if (!(Test-Path -LiteralPath $keyPath)) {
    # ProcessStartInfo preserves the empty passphrase argument on PowerShell 7.
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'Run this script with PowerShell 7 (pwsh).' }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = (Get-Command ssh-keygen.exe).Source
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    foreach ($argument in @('-q', '-t', 'ed25519', '-C', 'MHP ECS dedicated key', '-f', $keyPath, '-N', '')) {
        $startInfo.ArgumentList.Add($argument)
    }
    $process = [System.Diagnostics.Process]::Start($startInfo)
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw 'SSH key generation failed.' }
}
if (!(Test-Path -LiteralPath ($keyPath + '.pub'))) { throw 'Public key is missing; existing private key was not changed.' }
$existing = if (Test-Path -LiteralPath $configPath) { [System.IO.File]::ReadAllText($configPath) } else { '' }
if ($existing -match '(?im)^Host\s+.*\bmhp-ecs\b') {
    throw 'mhp-ecs already exists; existing SSH configuration was preserved.'
}
$block = @'

# MHP: dedicated identity; host fingerprint must be verified before connection.
Host mhp-ecs
    HostName 118.178.92.58
    User root
    Port 22
    IdentityFile ~/.ssh/id_ed25519_mhp_ecs
    IdentitiesOnly yes
    StrictHostKeyChecking yes
    UserKnownHostsFile ~/.ssh/known_hosts_mhp
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ConnectTimeout 10

'@
[System.IO.File]::WriteAllText($configPath, $existing.TrimEnd() + "`n" + $block, $utf8)
Write-Output 'Local SSH configuration created: mhp-ecs'
Write-Output 'Public key (safe to install on your server):'
Get-Content -LiteralPath ($keyPath + '.pub')
& ssh-keygen.exe -lf ($keyPath + '.pub')
if ($LASTEXITCODE -ne 0) { throw 'Public key validation failed.' }
