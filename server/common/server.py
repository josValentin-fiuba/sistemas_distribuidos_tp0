import socket
import logging
import signal
import sys
import multiprocessing
from common.socket_utils import recv_all
from common.utils import *

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._client_sock = None
        self._clients_done_sockets = {}
        self._agencies = set()
        self.lock = multiprocessing.Manager().Lock()

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

        # Create a pool of workers
        pool = multiprocessing.Pool(processes=5)

        try:
            while True:
                self._client_sock = self.__accept_new_connection()
                pool.apply_async(self._handle_client_connection, (self._client_sock,))
        finally:
            self._server_socket.close()
            pool.close()
            pool.join()

    def _recv_end_signal(self, client_sock):
        data = recv_all(client_sock, 4)
        agency_id = int.from_bytes(data, byteorder="big", signed=False)
        data = recv_all(client_sock, 1)
        signal = bool(data[0])
        return agency_id, signal

    def _recv_bet(self, client_sock, agency_id):
        data = recv_all(client_sock, 4)
        name_len = int.from_bytes(data, byteorder="big", signed=False)
        data = recv_all(client_sock, 4)
        last_name_len = int.from_bytes(data, byteorder="big", signed=False)
        data = recv_all(client_sock, 4)
        birthdate_len = int.from_bytes(data, byteorder="big", signed=False)

        name = recv_all(client_sock, name_len).decode('utf-8')                
        last_name = recv_all(client_sock, last_name_len).decode('utf-8')                
        birthdate = recv_all(client_sock, birthdate_len).decode('utf-8')       

        data = recv_all(client_sock, 4)
        dni = int.from_bytes(data, byteorder="big", signed=False)
        data = recv_all(client_sock, 4)
        num = int.from_bytes(data, byteorder="big", signed=False)

        return Bet(str(agency_id), name, last_name, str(dni), birthdate, str(num))

    def _send_winners(self):
        logging.info(f"action: sorteo | result: success")
        all_bets = load_bets()

        winners_per_agency = {}
        for agency_id in self._clients_done_sockets.keys():
            winners_per_agency[agency_id] = []
        
        for bet in all_bets:
            if not has_won(bet):
                continue
            if bet.agency in winners_per_agency:
                winners_per_agency[bet.agency].append(bet)

        for agency_id, winners in winners_per_agency.items():
            agency_sock = self._clients_done_sockets[agency_id]
            agency_sock.sendall(len(winners).to_bytes(4, byteorder='big', signed=False))
            for bet in winners:
                agency_sock.sendall(int(bet.document).to_bytes(4, byteorder='big', signed=False))

        self._clients_done_sockets = {}
    
    def _handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        bets_in_batch = []
        try:
            agency_id, end_signal = self._recv_end_signal(client_sock)
            with self.lock:
                self._agencies.add(agency_id)
            
            if end_signal:
                logging.info(f"No bets to receive. Agency({agency_id}) sent end signal")
                with self.lock:
                    self._clients_done_sockets[agency_id] = client_sock
                    if len(self._clients_done_sockets) == len(self._agencies):
                        self._send_winners()
                return

            while True:
                bet = self._recv_bet(client_sock, agency_id)
                bets_in_batch.append(bet)
            
        except ConnectionError as e:
            with self.lock:
                store_bets(bets_in_batch)
            logging.info(f"Connection closed {e}")
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets_in_batch)}")
            client_sock.close()

        except OSError as e:
            logging.error(f"action: receive_message | result: fail | error: {e}")
            logging.info(f"action: apuesta_recibida | result: fail | cantidad: {len(bets_in_batch)}")
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
