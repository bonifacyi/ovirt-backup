#!/usr/bin/env python

import socket
import os
import logging


LOG_FOLDER = os.getcwd()
LOG_FILE = os.path.join(LOG_FOLDER, 'socket_client.log')
logging.basicConfig(
    level=logging.INFO,
    filename=LOG_FILE,
    filemode='w',
    format='%(asctime)s | %(levelname)s | %(message)s',
)
UNIX_SOCKET = "/tmp/backup_unix_socket"

print("Connecting...")
if os.path.exists(UNIX_SOCKET):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    client.connect(UNIX_SOCKET)
    print("Ready.")
    print("Ctrl-C to quit.")
    print("Sending 'DONE' shuts down the server and quits.")
    while True:
        try:
            inp = input("> ")
            if inp != '':
                print("SEND:", inp)
                client.send(inp.encode('utf-8'))
                if "DONE" == inp:
                    print("Shutting down.")
                    break
                data = client.recv(1024).decode('utf-8')
                if not data:
                    break
                print(data)
        except KeyboardInterrupt as k:
            print("Shutting down...")
            client.close()
            break
        except NameError as e:
            print(e)
            break
else:
    print("Couldn't Connect!")
    print("Done")
