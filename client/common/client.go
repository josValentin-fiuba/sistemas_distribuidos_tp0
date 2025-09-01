package common

import (
	// "bufio"
	// "fmt"
	"net"
	"time"
	"github.com/op/go-logging"
	"os"
    "strconv"
	"bytes"
    "encoding/binary"
	"encoding/csv"
	"fmt"
	"io"
)

var log = logging.MustGetLogger("log")

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
	BatchMax	  int
}

// Struct to store a bet data
type Bet struct {
	name          string
	lastName  	  string
	dni    		  int
	birthDate     string
	number	  	  int
}

// Client Entity that encapsulates how
type Client struct {
	config ClientConfig
	conn   net.Conn
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config: config,
	}
	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
	}
	c.conn = conn
	return nil
}

// Returns the size in bytes of a Bet struct once serialized to be sent
func GetBetPacketSize(bet Bet) int{
	return 12 + len(bet.name) + len(bet.lastName) + len(bet.birthDate) + 8
}

// Sends a bet to the server
func (c *Client)SendBet(bet Bet) error {
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
	
	return WriteAll(c.conn, buf.Bytes())
}

// Reads a CSV record and parses it to a Bet struct
func ReadBet(record []string) (Bet, error) {
	var bet Bet
	if len(record) < 5 { // según cuántas columnas tenga tu CSV
        return bet, fmt.Errorf("Invalid line, with %d values, expected 5", len(record))
    }

	bet.name = record[0]
	bet.lastName = record[1]
	dni, err := strconv.Atoi(record[2])
	if err != nil {
		return bet, fmt.Errorf("Invalid DNI value: %s", record[2])
	}
	bet.dni = dni
	bet.birthDate = record[3]
	number, err := strconv.Atoi(record[4])
	if err != nil {
		return bet, fmt.Errorf("Invalid Number value: %s", record[4])
	}
	bet.number = number

	return bet, nil
}

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	agency_id, _ := strconv.Atoi(c.config.ID)
	f, err := os.Open(fmt.Sprintf(".data/agency-%d.csv", agency_id))
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()

	reader := csv.NewReader(f)
	
	done := false
	for !done {

		c.createClientSocket()
		bytesSent := 0
		for	 i := 0; i < c.config.BatchMax; i++ {
			record, err := reader.Read()
			if err == io.EOF {
				done = true
				break
			}
			if err != nil {
				log.Fatal(err)
			}
			// Process line (parsing column values to Bet)
			bet, err := ReadBet(record)
			if err != nil {
				log.Errorf("Invalid bet record, skipping | error: %v", err)
				continue
			}

			// Hard limit for batch size (8KB)
			if bytesSent + GetBetPacketSize(bet) > 8192 {
				log.Errorf("Invalid batch size, skipping")
				return
			}

			bytesSent += GetBetPacketSize(bet)

			err = c.SendBet(bet)
			
			if err != nil {
				log.Errorf("Couldn't send bet to server. id %v | error: %v",
					c.config.ID,
					err,
				)
				break
			}

			log.Infof("action: apuesta_enviada | result: success | dni: %v | numero: %v", bet.dni, bet.number)
		}

		c.conn.Close()
		time.Sleep(c.config.LoopPeriod)
	}
	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

// Shutdown Closes the client connection
func (c *Client) Shutdown() {
	if c.conn != nil {
		c.conn.Close()
	}
}
