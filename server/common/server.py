import socket
import logging
import signal
import sys
import multiprocessing
from common.utils import *
import common.protocol as protocol

class Server:
    def __init__(self, port, listen_backlog):
        manager = multiprocessing.Manager()

        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._max_workers = listen_backlog + 1 # (N_Agencies = Max workers = Listen backlog) + agencies alive timeout worker
        self._clients_done_sockets = manager.dict()
        self._agencies = manager.dict()
        self._lock = manager.Lock()
        self._cond = manager.Condition(self._lock)

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """

        pool = multiprocessing.Pool(processes=self._max_workers)

        pool.apply_async(self._wait_for_winners)

        # Register SIGTERM signal handler considering pool
        def sigterm_handler(signum, _):
            logging.info('closing server socket [sigterm]')
            self._server_socket.close()
            pool.terminate() # Terminate all worker processes (send SIGTERM to children)
            sys.exit(0) # Graceful exit on signal

        signal.signal(signal.SIGTERM, sigterm_handler)

        while True:
            client_sock = self.__accept_new_connection()
            pool.apply_async(self._handle_client_connection, (client_sock,))

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
            
        self._clients_done_sockets.clear()
    
    def _wait_for_winners(self):
        with self._cond:
            agencies_alive_result = self._cond.wait_for(lambda: len(self._agencies) == 5, timeout=3)

            if agencies_alive_result:
                logging.info("All agencies connected")
            else:
                logging.info("No more agencies will connect")

            while len(self._clients_done_sockets) < len(self._agencies):
                self._cond.wait() # Waiting for all conected agencies to finish

            logging.info(f"Time to send results! ({len(self._clients_done_sockets)} of {len(self._agencies)} agencies done)")
            self._send_winners()

    def _handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        
        # Each worker process should handle SIGTERM to close client socket and end gracefully
        def worker_sigterm_handler(signum, _):
            client_sock.close()
            sys.exit(0)
        signal.signal(signal.SIGTERM, worker_sigterm_handler)

        bets_in_batch = []
        try:
            agency_id, end_signal = protocol.recv_end_signal(client_sock)
            with self._cond:
                self._agencies[agency_id] = True
            
                if end_signal:
                    logging.info(f"No bets to receive. Agency({agency_id}) sent end signal")
                    self._clients_done_sockets[agency_id] = client_sock
                self._cond.notify_all()

            if end_signal:
                return
            
            while True:
                bet = protocol.recv_bet(client_sock, agency_id)
                bets_in_batch.append(bet)
            
        except ConnectionError as e:
            with self._lock:
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
