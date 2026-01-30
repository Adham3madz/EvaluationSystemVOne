
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' 1. Get location of this script
strScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptDir

' 2. Determine the WinPython Root (Up one level)
strWinPyDir = FSO.GetParentFolderName(strScriptDir)

' 3. Look for the Python directory (e.g., python-3.11.x.amd64)
strPythonExe = ""
If FSO.FolderExists(strWinPyDir) Then
    Set folder = FSO.GetFolder(strWinPyDir)
    For Each subfolder In folder.SubFolders
        ' Look for a folder starting with "python-" which contains python.exe
        If (Left(subfolder.Name, 7) = "python-") Or (subfolder.Name = "python") Then
            strCheckPath = subfolder.Path & "\python.exe"
            If FSO.FileExists(strCheckPath) Then
                strPythonExe = strCheckPath
                Exit For
            End If
        End If
    Next
End If

' 4. Fallback: If not found, use global "python" (or modify this line if you know the exact path)
If strPythonExe = "" Then 
    strPythonExe = "python"
End If

' 5. Run the command hidden
WshShell.Run """" & strPythonExe & """ app.py", 0
