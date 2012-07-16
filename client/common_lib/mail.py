import os, email, smtplib


def send(from_address, to_addresses, cc_addresses, subject, message_body):
    """
    Send out a plain old text email. It uses sendmail by default, but
    if that fails then it falls back to using smtplib.

    Args:
            from_address: the email address to put in the "From:" field
            to_addresses: either a single string or an iterable of
                          strings to put in the "To:" field of the email
            cc_addresses: either a single string of an iterable of
                          strings to put in the "Cc:" field of the email
            subject: the email subject
            message_body: the body of the email. there's no special
                          handling of encoding here, so it's safest to
                          stick to 7-bit ASCII text
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

    message = email.Message.Message()
    message["To"] = ", ".join(to_addresses)
    message["Cc"] = ", ".join(cc_addresses)
    message["From"] = from_address
    message["Subject"] = subject
    message.set_payload(message_body)

    server = smtplib.SMTP("localhost")
    server.sendmail(from_address, to_addresses + cc_addresses, message.as_string())
    server.quit()
