; This is a sample AutoIt script, based on the notepad1 sample script by Jonathan Bennett.
; It runs notepad, enters some text and exits.


; Exit with a nonzero exit status if the parameter equals 0.
; This is useful for functions that return 0 upon failure.
Func Assert($n)
    If $n = 0 Then Exit(1)
EndFunc

; Wait for a window to exist, activate it, and wait for it to become active.
; If timeout expires while waiting, exit with a nonzero exit status.
Func WaitForWindow($title, $text="", $timeout=60)
    Assert(WinWait($title, $text, $timeout))
    WinActivate($title, $text)
    Assert(WinWaitActive($title, $text, $timeout))
EndFunc

; Run Notepad
Assert(Run("notepad.exe"))

; Wait up to 10 seconds for Notepad to become active --
; it is titled "Untitled - Notepad" on English systems
WaitForWindow("Untitled - Notepad", "", 10)

; Now that the Notepad window is active type some text
Send("Hello from Notepad.{ENTER}1 2 3 4 5 6 7 8 9 10{ENTER}")
Sleep(500)
Send("+{UP 2}")
Sleep(500)

; Now quit by pressing Alt-f and then x (File menu -> Exit)
Send("!f")
Send("x")

; Now a screen will pop up and ask to save the changes, the window is called 
; "Notepad" and has some text "Yes" and "No"
WaitForWindow("Notepad", "", 10)
Send("n")

; Now wait for Notepad to close before continuing
WinWaitClose("Untitled - Notepad", "", 10)

; Finished!
