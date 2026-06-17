Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

logFile = scriptDir & "\vbs_log.txt"
Set log = fso.CreateTextFile(logFile, True)
log.WriteLine "VBS Start: " & Now
log.WriteLine "ScriptDir: " & scriptDir
log.Close

cmd = "cmd /c cd /d """ & scriptDir & """ && python -u quick_start.py >> service_output_vbs.txt 2>&1"
WshShell.Run cmd, 0, False

WScript.Sleep 12000

Set log = fso.OpenTextFile(logFile, 8)
log.WriteLine "VBS launched command: " & cmd
log.WriteLine "VBS Done: " & Now
log.Close

WScript.Sleep 500
