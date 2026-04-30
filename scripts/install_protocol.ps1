$vbsPath = 'C:\Users\KnyshovDmitry\appwin\scripts\open_net_folder.vbs'
$wsExe   = "$env:SystemRoot\System32\wscript.exe"

# /B — batch mode (без диалогов)
$cmd = "`"$wsExe`" /B `"$vbsPath`" `"%1`""

$base = 'HKCU:\SOFTWARE\Classes\opennet'

New-Item -Path $base -Force | Out-Null
Set-ItemProperty -Path $base -Name '(default)' -Value 'URL:Open Network Folder'
New-ItemProperty -Path $base -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
New-Item -Path "$base\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$base\shell\open\command" -Name '(default)' -Value $cmd

Write-Host 'OK: opennet:// -> wscript.exe (silent) -> powershell -> explorer'
Write-Host $cmd
