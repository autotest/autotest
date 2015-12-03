#!/usr/bin/python

import unittest

import mail
# the email module has some weird behavior change among py 2.4/2.6
# pylint: disable=E0611
from email import Message


class test_data:
    mail_host = None
    mail_port = None
    mail_connect = False
    mail_from_address = None
    mail_to_address = None
    mail_message = None
    login = False


# we define our needed mock SMTP
class SMTP(object):

    def __init__(self, host=None, port=25):
        test_data.mail_host = host
        test_data.mail_port = port

        if test_data.mail_host:
            self.connect(test_data.mail_host, test_data.mail_port)

    def connect(self, host, port):
        test_data.mail_connect = True

    def quit(self):
        test_data.mail_connect = False

    def login(self, user, password):
        test_data.login = True

    def sendmail(self, from_address, to_address, message):
        test_data.mail_from_address = from_address
        test_data.mail_to_address = to_address
        test_data.mail_message = message


class mail_test(unittest.TestCase):
    cached_SMTP = None

    def setUp(self):
        # now perform the slip
        self.cached_SMTP = mail.smtplib.SMTP
        mail.smtplib.SMTP = SMTP

    def tearDown(self):
        # now put things back
        mail.smtplib.SMTP = self.cached_SMTP

    def test_send_message(self):
        message = Message.Message()
        message["To"] = "you"
        message["Cc"] = "them"
        message["From"] = "me"
        message["Subject"] = "hello"
        message.set_payload("Hello everybody!")

        smtp_info = {'server': 'stmp.foo.com',
                     'port': 25,
                     'user': 'brian',
                     'password': 'judealiberationfront'}

        mail.send(from_address="me", to_addresses="you", cc_addresses="them",
                  subject="hello", body="Hello everybody!", smtp_info=smtp_info)

        self.assertEquals("me", test_data.mail_from_address)
        self.assertEquals(["you", "them"], test_data.mail_to_address)
        self.assertEquals(message.as_string(), test_data.mail_message)


# this is so the test can be run in standalone mode
if __name__ == '__main__':
    unittest.main()
