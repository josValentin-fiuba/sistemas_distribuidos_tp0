import socket
import logging
import signal
import sys
from common.utils import *
import common.protocol as protocol

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._client_sock = None

    def sigterm_handler(self, signum, _):
        logging.info('closing server socket [sigterm]')
        self._server_socket.close()
        if self._client_sock:
            logging.info('closing connected client socket [sigterm]')
            self._client_sock.close()
        sys.exit(0) # Graceful exit on signal

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """

        # Register SIGTERM signal handler
        signal.signal(signal.SIGTERM, self.sigterm_handler)

        agency_index = 0
        while True:
            self._client_sock = self.__accept_new_connection()
            self.__handle_client_connection(self._client_sock, agency_index)
            agency_index += 1

    def __handle_client_connection(self, client_sock, agency_index):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        bets_in_batch = []
        try:
            agency_id, batch_count = protocol.recv_batch_count(client_sock)

            for _ in range(batch_count):
                bet = protocol.recv_bet(client_sock, agency_id)
                bets_in_batch.append(bet)
            
            store_bets(bets_in_batch)
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets_in_batch)}")
            
        except OSError as e:
            # logging.error("action: receive_message | result: fail | error: {e}")
            logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets_in_batch)}")
        finally:
            client_sock.close()

    def __accept_new_connection(self):
        """
        Accept new connections

        Function blocks until a connection to a client is made.
        Then connection created is printed and returned
        """

        # Connection arrived
        logging.info('action: accept_connections | result: in_progress')
        c, addr = self._server_socket.accept()
        logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
        return c
