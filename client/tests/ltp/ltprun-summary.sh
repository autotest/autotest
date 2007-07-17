#! /bin/sh
# summary of LTP suite 'logfile' results:
# count "execution: PASS|FAIL|WARN|BROK|RETR|CONF(config error)";
# count "\.c:.*error:" for build errors (lines);

logfile=${1-logfile}
echo "Using logfile=$logfile"

TMPFILE="$logfile.$$"
prtag2tag.pl test_output execution_status $logfile >$TMPFILE

##build_failed=`grep "build: FAILED" $TMPFILE | wc -l`
build_errors=`grep "\.c:.*error:"  $TMPFILE | wc -l`

run_passed=`grep "^\w* *[[:digit:]]* *PASS *:"  $TMPFILE | wc -l`
run_warned=`grep "^\w* *[[:digit:]]* *WARN *:"  $TMPFILE | wc -l`
run_broken=`grep "^\w* *[[:digit:]]* *BROK *:"  $TMPFILE | wc -l`
run_failed=`grep "^\w* *[[:digit:]]* *FAIL *:"  $TMPFILE | wc -l`
run_retire=`grep "^\w* *[[:digit:]]* *RETR *:"  $TMPFILE | wc -l`
run_cfgerr=`grep "^\w* *[[:digit:]]* *CONF *:"  $TMPFILE | wc -l`
# ignore INFO lines

printf "Build errors:  %s lines\n" $build_errors
printf "Pass:          %s\n" $run_passed
printf "Warning:       %s\n" $run_warned
printf "Broken:        %s\n" $run_broken
printf "Retired:       %s\n" $run_retire	## NB: not counted in any totals
printf "Fail:          %s\n" $run_failed
printf "Config error:  %s\n" $run_cfgerr

passing=$((run_passed + run_warned))
notpass=$((run_broken + run_cfgerr + run_failed))
total=$((notpass + passing))
score=$((1000 * passing))	# convert to percent.decimal
score=$((score + total / 2))	# rounding
if [ $total -eq 0 ]; then
	score=0
else
	score=$((score / total))
fi
fraction=$((score % 10))
score=$((score / 10))
printf "SCORE.ltp:        %d.%d\n" $score $fraction
rm -f $TMPFILE
