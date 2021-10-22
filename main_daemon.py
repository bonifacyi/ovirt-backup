import os
import daemon
import argparse
from daemon import pidfile
from functools import partial

from backup_service import main_server
from res import app_logger
logger = app_logger.get_logger(__name__)
debug_p = False


def start_daemon(pid_file, partial_function):
    tmp = os.path.join(os.getcwd(), 'res', 'tmp')

    with daemon.DaemonContext(
        working_directory=tmp,
        umask=0o002,
        pidfile=pidfile.TimeoutPIDLockFile(pid_file, -1),
    ) as context:
        partial_function()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Example daemon in Python")
    parser.add_argument('-p', '--pid-file', default='/var/run/xrdp/custom_socket.pid')
    args = parser.parse_args()

    function = partial(main_server)
    start_daemon(pid_file=args.pid_file, partial_function=function)
