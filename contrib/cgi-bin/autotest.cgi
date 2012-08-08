#!/bin/sh
#
# (1) drop this file into /var/www/cgi-bin/
# (2) drop a file into /etc/httpd/conf.d/ with this content:
#
# Alias /autotest /autotest/autotest/client/results
# <Directory "/autotest/autotest/client/results">
#         Allow from all
#         Options +Indexes
#         IndexOptions +FancyIndexing
#         AddType text/plain .DEBUG
#         AddType text/plain .ERROR
#         AddType text/plain .INFO
#         AddType text/plain .WARNING
#         AddType text/plain .log
# </Directory>
#
# (3) adapt paths
# (4) restart apache
# (5) point your browser to http://host/cgi-bin/autotest.cgi
# (6) watch autotest working

# config
dir="/autotest/autotest/client/results"
url="http://${SERVER_NAME}/autotest"

##########################################################################
# go

# finished?
if test -f "$dir/default/job_report.html"; then
	echo "Status: 302 all done"
	echo "Location: $url/default/job_report.html"
	echo ""
	exit 0
fi

current="$(ls -t $dir/default/*/status | head -1)"
current="${current#$dir/default/}"
current="${current%/status}"
if test "$current" = ""; then
	current="tests_not_running_yet"
fi

# header
cat <<EOF
Content-Type: text/html
Refresh: 5; http://${SERVER_NAME}${REQUEST_URI}

<html>
<head>
<title>autotest @ ${SERVER_NAME}</title>
<style type="text/css">
<!--

h1 {
	font-size: 120%;
	font-weight: bold;
	border-bottom: 2px black solid;
}
h2 {
	clear: both;
	font-size: 100%;
	font-weight: bold;
	margin: 0;
	padding: 1em 0 0 0;
}
pre {
	padding: 0 2ex;
	margin: 0;
}

a {
	color: darkblue;
	text-decoration: none
}
a:hover {
	color: blue;
	text-decoration: underline
}

div.small {
	float: left;
	padding: 3px;
	margin: 3px;
	background: #c0c0c0;
	font-size: 80%;
	z-index: 1;
}
div.small img.small {
	width: 240px;
	height: 180px;
	border: 3px black solid;
}
div.small div.big {
	display: none;
}

div.small:hover div.big {
	position: absolute;
	text-align: center;
	left: 5px;
	top: 5px;
	display: block;
}

div.small:hover div.big img.big {
	border: 12px black solid;
}

-->
</style>
</head>
<body>
<h1><a href="$url/default/$current/">$current</a></h1>
EOF

# screen shot
for sdir in $(ls -d $dir/default/$current/debug/screendumps_* 2>/dev/null); do
        guest="${sdir#$dir/default/$current/debug/screendumps_}"
	screen="$(ls -t $sdir/*.jpg | head -1)"
	test -f "$screen" || continue
	screen="${screen/$dir/$url}"
	echo "<div class=\"small\">"
	echo " <img class=\"small\"src=\"$screen\">"
	echo " <br>$guest: $(basename $screen)"
	echo " <div class=\"big\">"
	echo "  <img class=\"big\" src=\"$screen\">"
	echo " </div>"
	echo "</div>"
done

# logs (most recently updated first)
cd $dir/default/$current/debug
for logfile in $(ls -t *.INFO *.DEBUG *.log); do
	test -s "$logfile" || continue
	link="$url/default/$current/debug/$logfile"
	echo "<h2><a href=\"$link\">$logfile</a></h2>"
	echo "<pre>"
	tail -n 8 "$logfile" \
	    | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
	echo "</pre>"
done

# footer
cat <<EOF
</body>
</html>
EOF
