#!/usr/bin/python

import sys, os
import MySQLdb
import urllib, db, unique_cookie

uid = unique_cookie.unique_id('tko_history')


def body():
	db_obj = db.db()
	condition = "uid='%s'" % uid
	where = (condition,[])
	try:
		rows = db_obj.select("time_created,user_comment,url",
				     "query_history", where)
	except MySQLdb.ProgrammingError, err:
		print err
		rows = ()

	for row in rows:
		(time_created, user_comment, tko_url) = row
		print "<hr>"
		print time_created + "&nbsp;"*3
		print user_comment + "<br>"
		print '<a href="%s">%s</a>' % (tko_url, tko_url)
	print '<hr>'


def main():
	print "Content-type: text/html\n"
	print
	# create the actual page
	print '<html><head><title>'
	print 'History of TKO usage'
	print '</title></head><body>'
	body()
	print '</body></html>'


main()


