' Launch OpenRouter Dashboard without a console window.
' Install dependencies once first:  pip install -r requirements.txt
Option Explicit

Dim sh, fso, dir, mainPy, py
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir

mainPy = fso.BuildPath(dir, "main.py")
If Not fso.FileExists(mainPy) Then
  MsgBox "main.py not found:" & vbCrLf & dir, 16, "OpenRouter Dashboard"
  WScript.Quit 1
End If

' Prefer pythonw (no console); fall back to python
py = Which("pythonw.exe")
If py = "" Then py = Which("python.exe")
If py = "" Then
  MsgBox "Python not found on PATH." & vbCrLf & vbCrLf & _
         "Install Python 3.9+, then run:" & vbCrLf & _
         "  pip install -r requirements.txt", 16, "OpenRouter Dashboard"
  WScript.Quit 1
End If

' 0 = hidden console (useful if python.exe is the fallback)
sh.Run """" & py & """ """ & mainPy & """", 0, False

Function Which(cmd)
  Dim exec, line
  Set exec = sh.Exec("%ComSpec% /c where " & cmd & " 2>NUL")
  Do While exec.Status = 0
    WScript.Sleep 10
  Loop
  If Not exec.StdOut.AtEndOfStream Then
    line = Trim(exec.StdOut.ReadLine)
  End If
  If line <> "" And fso.FileExists(line) Then
    Which = line
  Else
    Which = ""
  End If
End Function
