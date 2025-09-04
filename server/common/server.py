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
        self._clients_done_sockets = {}
        self._agencies = set()

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

        while True:
            self._client_sock = self.__accept_new_connection()
            self.__handle_client_connection(self._client_sock)

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
            protocol.send_agency_winners(agency_sock, winners)
            agency_sock.close()

        self._clients_done_sockets = {}
    
    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        bets_in_batch = []
        try:
            agency_id, batch_count, is_last_batch = protocol.recv_batch_count(client_sock)

            for _ in range(batch_count):
                bet = protocol.recv_bet(client_sock, agency_id)
                bets_in_batch.append(bet)
            
            store_bets(bets_in_batch)
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets_in_batch)}")

            self._agencies.add(agency_id)

            if is_last_batch:
                logging.info(f"Agency({agency_id}) LAST BATCH")
                # Let the socket open to send winners
                self._clients_done_sockets[agency_id] = client_sock
                if len(self._clients_done_sockets) == len(self._agencies):
                    self._send_winners()
            else:
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
