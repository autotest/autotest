#!/usr/bin/python

import os, cgi, cgitb, time, urllib
import db, unique_cookie

## setting script globals
form = cgi.FieldStorage()
if 'label' in form.keys():
    comment = form['label'].value
else:
    comment = ''
dict_url = {}
for key in form.keys():
    dict_url[key] = form[key].value

tm = time.asctime()
uid = unique_cookie.unique_id('tko_history')
HTTP_REFERER = os.environ.get('HTTP_REFERER')
if HTTP_REFERER is None:
    ## fall back strategy for proxy connection
    ## substitute relative url
    HTTP_REFERER = 'compose_query.cgi?' + urllib.urlencode(dict_url)    


class QueryHistoryError(Exception):
    pass


def log_query():
    db_obj = db.db()
    data_to_insert = {'uid':uid, 'time_created':tm,
              'user_comment':comment, 'url':HTTP_REFERER }
    try:
        db_obj.insert('query_history', data_to_insert)
    except:
        raise QueryHistoryError("Could not save query")


def delete_query(time_stamp):
    ## query is marked for delete by time stamp
    db_obj = db.db()
    data_to_delete = {'time_created':time_stamp}
    try:
        db_obj.delete('query_history', data_to_delete)
    except Exception:
        raise QueryHistoryError("Could not delete query")
    

def body():
    if not 'delete' in dict_url.keys():
        log_query()
        print '<b>%s</b><br><br>' % "Your query has been saved"
        print 'time: %s<br>' % tm
        print 'comments: %s<br><br>' % comment
    else:
        ## key 'delete' has arg value of time_stamp
        ## which identifies the query to be deleted
        time_stamp = dict_url['delete']
        delete_query(time_stamp)
        print '<b>%s</b><br><br>' % "Your query has been deleted"

    print '<a href="query_history.cgi">View saved queries</a>&nbsp;&nbsp;'
    print '<br><br>'
    if not 'delete' in dict_url.keys():
        print '<a href="%s">Back to Autotest</a><br>' % HTTP_REFERER
    else:
        print '<a href="compose_query.cgi">Autotest Results</a><br>'


def main():
    print "Content-type: text/html\n"
    print '<html><head><title>'
    print '</title></head>'
    print '<body>'
    body()
    print '</body>'
    print '</html>'


main()



