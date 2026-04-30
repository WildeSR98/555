' Запускает PowerShell скрипт полностью скрыто — без мигания окна
' Скрипт лежит рядом с этим VBS файлом (можно на сетевой шаре)

Dim ps1Path, psExe, url, cmd, scriptDir

url       = WScript.Arguments(0)
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
ps1Path   = scriptDir & "open_net_folder.ps1"
psExe     = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

cmd = psExe & " -ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -File """ & ps1Path & """ """ & url & """"

Dim shell
Set shell = CreateObject("WScript.Shell")
' 0 = скрытое окно, False = не ждать завершения
shell.Run cmd, 0, False
Set shell = Nothing
