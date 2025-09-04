package common

import (
	"net"
    "encoding/binary"
	"bytes"
)

const INT_SIZE = 4

// Converts a boolean to a byte (1 for true, 0 for false)
func BoolToByte(v bool) byte {
    if v {
        return 1
    }
    return 0
}

// Returns the size in bytes of a Bet struct once serialized to be sent
func GetBetPacketSize(bet Bet) int{
	return 3 * INT_SIZE + len(bet.name) + len(bet.lastName) + len(bet.birthDate) + 2 * INT_SIZE
}

// Sends the batch count to the server (4 bytes agencyId + 4 bytes batchCount + 1 byte isLastBatch)
func SendBatchCount(conn net.Conn, agencyId int, batchCount int, isLastBatch bool) error {
	buf := new(bytes.Buffer)
	binary.Write(buf, binary.BigEndian, int32(agencyId))
	binary.Write(buf, binary.BigEndian, int32(batchCount))
	err := buf.WriteByte(BoolToByte(isLastBatch))
	if(err != nil){
		return err
	}
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

// Waits for the server response with the winners
func GetWinnersResponse(conn net.Conn) ([]int, error) {
	// Read number of winners (4 bytes)
	winnersCountBytes, err := ReadAll(conn, INT_SIZE)
	if err != nil {
		return nil, err
	}
	winnersCount := int(binary.BigEndian.Uint32(winnersCountBytes))

	winners := make([]int, winnersCount)
	for i := 0; i < winnersCount; i++ {
		// Read winner dni (4 bytes)
		dniBytes, err := ReadAll(conn, INT_SIZE)
		if err != nil {
			return nil, err
		}
		dni := binary.BigEndian.Uint32(dniBytes)
		winners[i] = int(dni)
	}

	return winners, nil
}