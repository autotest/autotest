import logging
import os

import aexpect

import remote
import utils


def get_public_key():
    """
    Return a valid string ssh public key for the user executing autoserv or
    autotest. If there's no DSA or RSA public key, create a DSA keypair with
    ssh-keygen and return it.

    :returns: a ssh public key
    :rtype: str
    """

    ssh_conf_path = os.path.expanduser('~/.ssh')

    dsa_public_key_path = os.path.join(ssh_conf_path, 'id_dsa.pub')
    dsa_private_key_path = os.path.join(ssh_conf_path, 'id_dsa')

    rsa_public_key_path = os.path.join(ssh_conf_path, 'id_rsa.pub')
    rsa_private_key_path = os.path.join(ssh_conf_path, 'id_rsa')

    has_dsa_keypair = (os.path.isfile(dsa_public_key_path) and
                       os.path.isfile(dsa_private_key_path))
    has_rsa_keypair = (os.path.isfile(rsa_public_key_path) and
                       os.path.isfile(rsa_private_key_path))

    if has_dsa_keypair:
        logging.info('DSA keypair found, using it')
        public_key_path = dsa_public_key_path

    elif has_rsa_keypair:
        logging.info('RSA keypair found, using it')
        public_key_path = rsa_public_key_path

    else:
        logging.info('Neither RSA nor DSA keypair found, '
                     'creating DSA ssh key pair')
        utils.system('ssh-keygen -t dsa -q -N "" -f %s' % dsa_private_key_path)
        public_key_path = dsa_public_key_path

    public_key = open(public_key_path, 'r')
    public_key_str = public_key.read()
    public_key.close()

    return public_key_str


def get_remote_public_key(session):
    """
    Return a valid string ssh public key for the user executing autoserv or
    autotest. If there's no DSA or RSA public key, create a DSA keypair with
    ssh-keygen and return it.

    :param session: A ShellSession for remote host
    :returns: a ssh public key
    :rtype: str
    """
    session.cmd_output("mkdir -p ~/.ssh")
    session.cmd_output("chmod 700 ~/.ssh")

    ssh_conf_path = "~/.ssh"
    dsa_public_key_path = os.path.join(ssh_conf_path, 'id_dsa.pub')
    dsa_private_key_path = os.path.join(ssh_conf_path, 'id_dsa')

    rsa_public_key_path = os.path.join(ssh_conf_path, 'id_rsa.pub')
    rsa_private_key_path = os.path.join(ssh_conf_path, 'id_rsa')

    dsa_public_s = session.cmd_status("ls %s" % dsa_public_key_path)
    dsa_private_s = session.cmd_status("ls %s" % dsa_private_key_path)
    rsa_public_s = session.cmd_status("ls %s" % rsa_public_key_path)
    rsa_private_s = session.cmd_status("ls %s" % rsa_private_key_path)

    has_dsa_keypair = dsa_public_s == 0 and dsa_private_s == 0
    has_rsa_keypair = rsa_public_s == 0 and rsa_private_s == 0

    if has_dsa_keypair:
        logging.info('DSA keypair found on %s, using it', session)
        public_key_path = dsa_public_key_path

    elif has_rsa_keypair:
        logging.info('RSA keypair found on %s, using it', session)
        public_key_path = rsa_public_key_path

    else:
        logging.info('Neither RSA nor DSA keypair found, '
                     'creating DSA ssh key pair')
        session.cmd('ssh-keygen -t dsa -q -N "" -f %s' % dsa_private_key_path)
        public_key_path = dsa_public_key_path

    return session.cmd_output("cat %s" % public_key_path)


def setup_ssh_key(hostname, user, password, port=22):
    '''
    Setup up remote login in another server by using public key

    :param hostname: the server to login
    :type hostname: str
    :param user: user to login
    :type user: str
    :param password: password
    :type password: str
    :param port: port number
    :type port: int
    '''
    logging.debug('Performing SSH key setup on %s:%d as %s.' %
                  (hostname, port, user))

    try:
        public_key = get_public_key()
        session = remote.remote_login(client='ssh', host=hostname, port=port,
                                      username=user, password=password,
                                      prompt=r'[$#%]')
        session.cmd_output('mkdir -p ~/.ssh')
        session.cmd_output('chmod 700 ~/.ssh')
        session.cmd_output("echo '%s' >> ~/.ssh/authorized_keys; " %
                           public_key)
        session.cmd_output('chmod 600 ~/.ssh/authorized_keys')
        logging.debug('SSH key setup complete.')
    except Exception as err:
        logging.debug('SSH key setup has failed: %s', err)
        try:
            session.close()
        except:
            pass


def setup_remote_ssh_key(hostname1, user1, password1,
                         hostname2=None, user2=None, password2=None,
                         port=22):
    '''
    Setup up remote to remote login in another server by using public key
    If hostname2 is not supplied, setup to local.

    :param hostname1: the server wants to login other host
    :param hostname2: the server to be logged in
    :type hostname: str
    :param user: user to login
    :type user: str
    :param password: password
    :type password: str
    :param port: port number
    :type port: int
    '''
    logging.debug('Performing SSH key setup on %s:%d as %s.' %
                  (hostname1, port, user1))

    try:
        session1 = remote.remote_login(client='ssh', host=hostname1, port=port,
                                       username=user1, password=password1,
                                       prompt=r'[$#%]')
        public_key = get_remote_public_key(session1)

        if hostname2 is None:
            # Simply create a session to local
            session2 = aexpect.ShellSession("sh", linesep='\n', prompt='#')
        else:
            session2 = remote.remote_login(client='ssh', host=hostname2,
                                           port=port, username=user2,
                                           password=password2,
                                           prompt=r'[$#%]')
        session2.cmd_output('mkdir -p ~/.ssh')
        session2.cmd_output('chmod 700 ~/.ssh')
        session2.cmd_output("echo '%s' >> ~/.ssh/authorized_keys; " %
                            public_key)
        session2.cmd_output('chmod 600 ~/.ssh/authorized_keys')
        logging.debug('SSH key setup on %s complete.', session2)
    except Exception as err:
        logging.debug('SSH key setup has failed: %s', err)
        try:
            session1.close()
            session2.close()
        except:
            pass
