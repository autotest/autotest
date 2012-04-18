#!/usr/bin/python

import unittest
import mail, email

class test_data:
    mail_host = None
    mail_port = None
    mail_connect = False
    mail_from_address = None
    mail_to_address = None
    mail_message = None


# we define our needed mock SMTP
class SMTP:
    def __init__(self, host=None, port=25):
        test_data.mail_host = host
        test_data.mail_port = port

        if test_data.mail_host:
            self.connect(test_data.mail_host, test_data.mail_port)


    def connect(self, host, port):
        test_data.mail_connect = True


    def quit(self):
        test_data.mail_connect = False


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
        message = email.Message.Message()
        message["To"] = "you"
        message["Cc"] = "them"
        message["From"] = "me"
        message["Subject"] = "hello"
        message.set_payload("Hello everybody!")

        mail.send("me", "you", "them", "hello", "Hello everybody!")
        self.assertEquals("me", test_data.mail_from_address)
        self.assertEquals(["you","them"], test_data.mail_to_address)
        self.assertEquals(message.as_string(), test_data.mail_message)


# this is so the test can be run in standalone mode
if __name__ == '__main__':
    unittest.main()
