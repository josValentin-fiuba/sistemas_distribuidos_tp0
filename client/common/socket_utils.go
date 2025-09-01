package common

import (
	"net"
	"io"
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

// Read exactly n bytes from conn
// If the peer closes the connection or an error occurs before n bytes are received returns an error
// Avoids short reads
func ReadAll(conn net.Conn, n int) ([]byte, error) {
	buf := make([]byte, n)
	total := 0
	for total < n {
		recvLen, err := conn.Read(buf[total:])
		if err != nil {
			return nil, err
		}
		if recvLen == 0 {
			return nil, io.ErrUnexpectedEOF
		}
		total += recvLen
	}
	return buf, nil
}
