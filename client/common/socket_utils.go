package common

import (
	"net"
)

// Write a message to socket
// If a problem arises in the communication with the peer, returns an error
// Avoids short writes
func WriteAll(conn net.Conn, data []byte) error {
	total := 0
	for total < len(data) {
		n, err := conn.Write(data[total:])
		if err != nil {
			return err
		}
		total += n
	}
	return nil
}