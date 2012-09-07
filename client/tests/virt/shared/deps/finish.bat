:check_net
if [%2]==[] goto check_process

set ping_host=%2
echo Check network status > COM1
ping %ping_host%

if errorlevel 1 goto check_net

:check_process
if [%1]==[] goto end

set process=%1
echo Check %process% status >  COM1
tasklist /FO List>  C:\log
type C:\log|find "%process%"

if errorlevel 1 goto end
if errorlevel 0 goto check_process

:end
echo Post set up finished>  COM1
