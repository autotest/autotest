"""
Notification email library.

Aims to replace a bunch of different email module wrappers previously used.
"""
import email
import logging
import os
import re
import smtplib
import socket
import time
import traceback

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared.settings import settings


DEFAULT_FROM_EMAIL = "autotest-grid@no-reply.com"


def _process_to_string(to_string):
    """
    Process a string containing email addresses. Separators: ',' ';' ':'

    :param to_string: String containing email addresses.
    :return: List with email addresses.
    """
    return [x for x in re.split('\s|,|;|:', to_string) if x]


def send(from_address, to_addresses, cc_addresses, subject, body,
         smtp_info, html=None):
    """
    Send out an email.

    Args:
            from_address: The email address to put in the "From:" field.
            to_addresses: Either a single string or an iterable of
                          strings to put in the "To:" field of the email.
            cc_addresses: Either a single string of an iterable of
                          strings to put in the "Cc:" field of the email.
            subject: The email subject.
            body: The body of the email. there's no special
                          handling of encoding here, so it's safest to
                          stick to 7-bit ASCII text.
            smtp_info: Dictionary with SMTP info.
            html: Optional HTML content of the message.
    """
    # addresses can be a tuple or a single string, so make them tuples
    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]
    else:
        to_addresses = list(to_addresses)
    if isinstance(cc_addresses, str):
        cc_addresses = [cc_addresses]
    else:
        cc_addresses = list(cc_addresses)

    if html:
        message = email.mime.multipart.MIMEMultipart('alternative')
        message["To"] = ", ".join(to_addresses)
        message["Cc"] = ", ".join(cc_addresses)
        message["From"] = from_address
        message["Subject"] = subject
        message.attach(email.mime.text.MIMEText(body, 'plain'))
        message.attach(email.mime.text.MIMEText(html, 'html'))
    else:
        message = email.Message.Message()
        message["To"] = ", ".join(to_addresses)
        message["Cc"] = ", ".join(cc_addresses)
        message["From"] = from_address
        message["Subject"] = subject
        message.set_payload(body)

    if not smtp_info['port']:
        smtp_info['port'] = 25

    try:
        if smtp_info['server']:
            mailer = smtplib.SMTP(smtp_info['server'], smtp_info['port'])
        else:
            logging.info("No SMTP server specified, will try to connect to "
                         "the local MTA")
            mailer = smtplib.SMTP()

        try:
            if smtp_info.get('user'):
                mailer.login(smtp_info['user'], smtp_info['password'])
            mailer.sendmail(from_address, to_addresses + cc_addresses,
                            message.as_string())
        finally:
            try:
                mailer.quit()
            except:
                logging.exception('mailer.quit() failed:')

    except Exception:
        logging.exception('Sending email failed:')


class EmailNotificationManager(object):

    """
    Email notification facility, for use in things like the autotest scheduler.

    This facility can use values defined in the autotest settings
    (global_config.ini) to conveniently send notification emails to the admin
    of an autotest module.
    """

    def __init__(self, module="scheduler"):
        """
        Initialize an email notification manager.

        :param subsystem: String describing the module this manager is
            handling. Example: 'scheduler'.
        """
        self.module = module
        self.email_queue = []

        self.html_email = settings.get_value("NOTIFICATION",
                                             "html_notify_email",
                                             type=bool,
                                             default=False)

        self.from_email = settings.get_value("NOTIFICATION",
                                             "notify_email_from",
                                             default=DEFAULT_FROM_EMAIL)

        self.grid_admin_email = settings.get_value("NOTIFICATION",
                                                   "grid_admin_email",
                                                   default='')

        server = settings.get_value("EMAIL", "smtp_server", default='localhost')
        port = settings.get_value("EMAIL", "smtp_port", default=None)
        user = settings.get_value("EMAIL", "smtp_user", default=None)
        password = settings.get_value("EMAIL", "smtp_password", default=None)

        self.smtp_info = {'server': server,
                          'port': port,
                          'user': user,
                          'password': password}

    def set_module(self, module):
        """
        Change the name of the module we're notifying for.
        """
        self.module = module

    def send(self, to_string, subject, body):
        """
        Send emails to the addresses listed in to_string.

        to_string is split into a list which can be delimited by any of:
            ';', ',', ':' or any whitespace
        """
        to_list = _process_to_string(to_string)
        if not to_list:
            return

        send(from_address=self.from_email, to_addresses=to_list, cc_addresses="",
             subject=subject, body=body, smtp_info=self.smtp_info,
             html=self.html_email)

    def send_admin(self, subject, body):
        """
        Send an email to this grid admin.
        """
        self.send(self.grid_admin_email, subject, body)

    def enqueue_admin(self, subject, message):
        """
        Enqueue an email to the test grid admin.
        """
        if not self.grid_admin_email:
            return

        body = 'Subject: ' + subject + '\n'
        body += "%s / %s / %s\n%s" % (socket.gethostname(),
                                      os.getpid(),
                                      time.strftime("%X %x"), message)
        self.email_queue.append(body)

    def enqueue_exception_admin(self, reason):
        """
        Enqueue an email containing an exception to the test grid admin.
        """
        logging.exception(reason)
        message = "EXCEPTION: %s\n%s" % (reason, traceback.format_exc())
        self.enqueue_admin("Exception on module %s" %
                           self.module, message)

    def send_queued_admin(self):
        """
        Send all queued emails to the test grid admin.
        """
        if not self.email_queue:
            return
        subject = ('Notifications (%s) from host: %s' %
                   (self.module, socket.gethostname()))
        separator = '\n' + '-' * 40 + '\n'
        body = separator.join(self.email_queue)

        self.send_admin(subject, body)
        # Reset the email queue.
        self.email_queue = []


manager = EmailNotificationManager()
