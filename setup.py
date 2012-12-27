# High level way of installing each autotest component
import client.setup
import frontend.setup
import cli.setup
import server.setup
import scheduler.setup
import database.setup
import tko.setup
import utils.setup
import mirror.setup

if __name__ == '__main__':
    client.setup.run()
    frontend.setup.run()
    cli.setup.run()
    server.setup.run()
    scheduler.setup.run()
    database.setup.run()
    tko.setup.run()
    utils.setup.run()
    mirror.setup.run()
