import socket
import logging
import signal
import sys
import multiprocessing
from common.utils import *
import common.protocol as protocol

class Server:
    def __init__(self, port, listen_backlog, max_agencies, agency_connection_timeout):
        manager = multiprocessing.Manager()

        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._max_agencies = max_agencies
        self._agencies = manager.dict()
        self._agencies_done = manager.dict()
        self._register_timedout = manager.Value('b', False)
        self._cond = manager.Condition()
        self._agency_connection_timeout = agency_connection_timeout

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """

        pool = multiprocessing.Pool(processes=self._max_agencies + 1) # (N_Agencies = Client workers) + Ending worker

        pool.apply_async(self._register_timeout_worker)

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

    def _send_winners(self, agency_sock, agency_id):
        logging.info(f"action: sorteo | result: success")
        all_bets = load_bets()

        agency_winners = []
        
        for bet in all_bets:
            if not has_won(bet):
                continue
            if bet.agency != agency_id:
                continue   
            agency_winners.append(bet)

        try:
            protocol.send_agency_winners(agency_sock, agency_winners)
        except OSError as e:
            logging.error(f"Couldn't send winners to agency {agency_id}. error: {e}")
        finally:
            agency_sock.close()
                
    def _register_timeout_worker(self):
        time.sleep(self._agency_connection_timeout)
        with self._cond:
            logging.info("Not expecting more agencies to connect")
            self._register_timedout.value = True
            self._cond.notify_all()

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
            agency_id, batch_count, is_last_batch = protocol.recv_batch_count(client_sock)

            for _ in range(batch_count):
                bet = protocol.recv_bet(client_sock, agency_id)
                bets_in_batch.append(bet)

            with self._cond:
                store_bets(bets_in_batch)
                logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets_in_batch)}")
                
                self._agencies[agency_id] = True

                if is_last_batch:
                    logging.info(f"Agency({agency_id}) LAST BATCH")
                    self._agencies_done[agency_id] = True

                self._cond.notify_all()

                if is_last_batch:
                    while not self._register_timedout.value or len(self._agencies_done) < len(self._agencies):
                        self._cond.wait()
                    self._send_winners(client_sock, agency_id)
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
