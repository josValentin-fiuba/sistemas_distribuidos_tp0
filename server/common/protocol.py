from common.utils import Bet
from common.socket_utils import *

INT_SIZE = 4
BOOL_SIZE = 1

def recv_end_signal(client_sock):
    data = recv_all(client_sock, INT_SIZE)
    agency_id = int.from_bytes(data, byteorder="big", signed=False)
    data = recv_all(client_sock, BOOL_SIZE)
    signal = bool(data[0])
    return agency_id, signal

def recv_bet(client_sock, agency_id):
    data = recv_all(client_sock, INT_SIZE)
    name_len = int.from_bytes(data, byteorder="big", signed=False)
    data = recv_all(client_sock, INT_SIZE)
    last_name_len = int.from_bytes(data, byteorder="big", signed=False)
    data = recv_all(client_sock, INT_SIZE)
    birthdate_len = int.from_bytes(data, byteorder="big", signed=False)

    name = recv_all(client_sock, name_len).decode('utf-8')                
    last_name = recv_all(client_sock, last_name_len).decode('utf-8')                
    birthdate = recv_all(client_sock, birthdate_len).decode('utf-8')       

    data = recv_all(client_sock, INT_SIZE)
    dni = int.from_bytes(data, byteorder="big", signed=False)
    data = recv_all(client_sock, INT_SIZE)
    num = int.from_bytes(data, byteorder="big", signed=False)

    return Bet(str(agency_id), name, last_name, str(dni), birthdate, str(num))

def send_agency_winners(agency_sock, winners):
    agency_sock.sendall(len(winners).to_bytes(INT_SIZE, byteorder='big', signed=False))
    for bet in winners:
        agency_sock.sendall(int(bet.document).to_bytes(INT_SIZE, byteorder='big', signed=False))