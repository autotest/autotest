#cs ---------------------------------------------
AutoIt Version: 3.1.1.0
Author: Qingtang Zhou <qzhou@redhat.com>

Script Function:
Install NT Testing TCP tool

Note: This script will sign "End-user license agreement" for user
#ce ---------------------------------------------

Func WaitWind($title)
        WinWait($title, "")

        If Not WinActive($title, "") Then
                WinActivate($title, "")
        EndIf
EndFunc

$FILE="msiexec /i ""D:\NTttcp\\NT Testing TCP Tool.msi"""
Run($FILE)

WaitWind("NT Testing TCP Tool")
WinWaitActive("NT Testing TCP Tool", "Welcome to the NT Testing TCP Tool Setup Wizard")
Send("!n")

WaitWind("NT Testing TCP Tool")
WinWaitActive("NT Testing TCP Tool", "License Agreement")
send("!a")
send("{ENTER}")

WaitWind("NT Testing TCP Tool")
WinWaitActive("NT Testing TCP Tool", "Select Installation Folder")
Send("{ENTER}")

WaitWind("NT Testing TCP Tool")
WinWaitActive("NT Testing TCP Tool", "Confirm Installation")
send("{ENTER}")

WinWaitActive("NT Testing TCP Tool", "Installation Complete")
send("!c")

