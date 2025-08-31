import socket
import logging
import signal
import sys
import struct
from common.socket_utils import recv_all
from common.utils import *

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

    def _recv_bet(self, client_sock, agency_index):
        data = recv_all(client_sock, 12)
        name_len, last_name_len, birthdate_len = struct.unpack('!III', data)

        name = recv_all(client_sock, name_len).decode('utf-8')                
        last_name = recv_all(client_sock, last_name_len).decode('utf-8')                
        birthdate = recv_all(client_sock, birthdate_len).decode('utf-8')       

        data = recv_all(client_sock, 8)
        dni, num = struct.unpack('!II', data)

        return Bet(str(agency_index), name, last_name, str(dni), birthdate, str(num))


    def __handle_client_connection(self, client_sock, agency_index):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            bet = self._recv_bet(client_sock, agency_index)
            store_bets([bet])
            logging.info(f'action: apuesta_almacenada | result: success | dni: {bet.document} | numero: {bet.number}')
            
        except ConnectionError as e:
            logging.log(f"Connection closed {e}")
        except OSError as e:
            logging.error("action: receive_message | result: fail | error: {e}")
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
