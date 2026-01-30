
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
strPath = FSO.GetParentFolderName(WScript.ScriptFullName)

' Set the working directory to the script's location
WshShell.CurrentDirectory = strPath

' Run using the SPECIFIC python that has Flask installed
' We use the absolute path to avoid "ModuleNotFoundError"
WshShell.Run """C:\Users\zizo\AppData\Local\Programs\Python\Python311\python.exe"" app.py", 0
