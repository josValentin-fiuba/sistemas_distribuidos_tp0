package common

import (
	"net"
    "encoding/binary"
	"bytes"
)

const INT_SIZE = 4

// Returns the size in bytes of a Bet struct once serialized to be sent
func GetBetPacketSize(bet Bet) int{
	return 12 + len(bet.name) + len(bet.lastName) + len(bet.birthDate) + 8
}

// Sends the batch count to the server (4 bytes agencyId + 4 bytes batchCount)
func SendBatchCount(conn net.Conn, agencyId int, batchCount int) error {
	buf := new(bytes.Buffer)
	binary.Write(buf, binary.BigEndian, int32(agencyId))
	binary.Write(buf, binary.BigEndian, int32(batchCount))
	return WriteAll(conn, buf.Bytes())
}

// Sends a bet to the server
func SendBet(conn net.Conn, bet Bet) error {
	buf := new(bytes.Buffer)

	// 3 ints (4b each one)
	binary.Write(buf, binary.BigEndian, int32(len(bet.name)))
	binary.Write(buf, binary.BigEndian, int32(len(bet.lastName)))
	binary.Write(buf, binary.BigEndian, int32(len(bet.birthDate)))
	
	buf.Write([]byte(bet.name))
	buf.Write([]byte(bet.lastName))
	buf.Write([]byte(bet.birthDate))

	binary.Write(buf, binary.BigEndian, int32(bet.dni))
	binary.Write(buf, binary.BigEndian, int32(bet.number))
	
	return WriteAll(conn, buf.Bytes())
}
