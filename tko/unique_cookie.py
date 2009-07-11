import os, random


def unique_id(cookie_key):
    """
    Find out if remote caller has cookie set on the key.
    If not, set cookie on client side: evaluate this key by a random string.
    ( unique user identifier )
    In both scenarios return value of the cookie, be it old or newly set one
    """
    uid = ''
    ## try to retrieve uid from Cookie
    if 'HTTP_COOKIE' in os.environ:
        ## parse os.environ['HTTP_COOKIE']
        cookies = os.environ['HTTP_COOKIE'].split(';')
        key = '%s=' % cookie_key
        uid_cookies = [c for c in cookies if c.strip().startswith(key)]

        if uid_cookies:
            assert(len(uid_cookies) == 1)
            uid_cookie = uid_cookies[0]
            uid = uid_cookie.replace(key, '')

    if not uid:
        uid = str(random.random())[2:16] # random string of 14 digits
        set_cookie_statement = 'Set-Cookie:%s=%s;' % (cookie_key, uid)
        set_cookie_statement += 'expires=Thu, 26-Dec-2013 22:03:25 GMT;'
        print set_cookie_statement

    return uid
