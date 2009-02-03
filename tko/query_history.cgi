#!/usr/bin/python

import sys, os
import common
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
    print '<table border="1">'
    ##  Display history starting with the most recent queries
    for row in reversed(rows):
        (time_created, user_comment, tko_url) = row
        print '<tr>'
        print '<td>&nbsp;%s&nbsp;</td>' % time_created
        print '<td>&nbsp;%s&nbsp;</td>' % user_comment
        dict_url = {'delete':time_created}
        link = 'save_query.cgi?' + urllib.urlencode(dict_url)
        print '<td>&nbsp;<a href="%s">Delete</a>&nbsp;</td>' % link
        print '<td><a href="%s">%s</a></td>' % (tko_url, tko_url)
        print '</tr>'
    print '</table>'

    last_recorded_query = ''
    if rows:
        (time_created, user_comment, last_recorded_query) = rows[-1]
    ## Link "Back to Autotest" on query history page
    back_link = os.environ.get('HTTP_REFERER')
    ## possible complications:
    ## a) HTTP_REFERER = None
    ## b) HTTP_REFERER is save_query page
    ## In both cases we still want to get to tko results.
    ## primary fall back: link to last_recorded_query
    ## secondary fall back: link to opening tko page
    if not "compose_query.cgi" in str(back_link):
        back_link = last_recorded_query
    if not back_link: ## e.g. history is empty and/or HTTP_REFERER unknown
        back_link = "compose_query.cgi"
    print '<br><a href="%s">Autotest Results</a><br>' % back_link


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
