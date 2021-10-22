import socket
import os

from broker import MessageBroker
from res import app_logger
logger = app_logger.get_logger(__name__)


def main_server(unix_socket="/tmp/oV_backup_unix_socket"):
    if os.path.exists(unix_socket):
        os.remove(unix_socket)

    logger.debug("Opening socket...")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    logger.debug('UNIX_SOCKET: ' + unix_socket)
    server.bind(unix_socket)

    logger.debug("Listening...")
    while True:
        try:
            data = server.recv(1024)
        except KeyboardInterrupt:
            break
        except:
            logger.exception('Listening socket error: ')
            break

        data = data.decode('utf-8')
        logger.debug(data)

        parser = MessageBroker(data)
        send_data = parser.run()
        server.send(send_data.encode('utf-8'))

    logger.debug("-" * 20)
    logger.debug("Shutting down...")
    server.close()
    os.remove(unix_socket)
    logger.debug("Done")


if __name__ == '__main__':
    main_server("/tmp/backup_unix_socket")
