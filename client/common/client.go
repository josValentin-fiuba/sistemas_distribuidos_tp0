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

// Params used by the client logic
type ClientParams struct {
	HandshakeMaxAttempts  int
	HandshakeAttemptDelay int
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
	params ClientParams
	conn   net.Conn
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig, params ClientParams) *Client {
	client := &Client{
		config: config,
		params: params,
	}
	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	c.conn = conn
	return err
}

// Initialize de client socket with resiliency, trying to connect
// to the server until success or until the max number of attempts
// is reached
func (c *Client) createClientSocketResilency() error {
	for i := 0; i < c.params.HandshakeMaxAttempts; i++ {
		err := c.createClientSocket()
		if err == nil {
			return nil
		}

		if i < c.params.HandshakeMaxAttempts-1 {
			time.Sleep(time.Duration(c.params.HandshakeAttemptDelay) * time.Millisecond)
		}
	}
	return fmt.Errorf("Connection error, max connect attempts reached")
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

// Converts a boolean to a byte (1 for true, 0 for false)
func BoolToByte(v bool) byte {
    if v {
        return 1
    }
    return 0
}

// Sends the end signal to the server (4 bytes agency_id + 1 byte signal)
func (c *Client)SendEndSignal(agency_id int, signal bool) error {
	buf := new(bytes.Buffer)
	binary.Write(buf, binary.BigEndian, int32(agency_id))
	err := buf.WriteByte(BoolToByte(signal))
	if(err != nil){
		return err
	}
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

// Waits for the server response with the winners
func (c *Client)GetWinnersResponse() ([]int, error) {
	// Read number of winners (4 bytes)
	winnersCountBytes, err := ReadAll(c.conn, 4)
	if err != nil {
		return nil, err
	}
	winnersCount := int(binary.BigEndian.Uint32(winnersCountBytes))

	winners := make([]int, winnersCount)
	for i := 0; i < winnersCount; i++ {
		// Read winner dni (4 bytes)
		dniBytes, err := ReadAll(c.conn, 4)
		if err != nil {
			return nil, err
		}
		dni := binary.BigEndian.Uint32(dniBytes)
		winners[i] = int(dni)
	}

	return winners, nil
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

		if err := c.createClientSocketResilency(); err != nil {
			log.Errorf("Couldn't connect to server. id %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}
		if err := c.SendEndSignal(agency_id, false); err != nil {
			log.Errorf("Couldn't send end signal(0) to server. id %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}

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
				c.conn.Close()
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

	if err := c.createClientSocketResilency(); err != nil {
		log.Errorf("Couldn't connect to server. id %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}

	if err := c.SendEndSignal(agency_id, true); err != nil {
		log.Errorf("Couldn't send end signal(1) to server. id %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}
	
	// Wait for the winner response
	winners, err := c.GetWinnersResponse()
	c.conn.Close()

	if err != nil {
		log.Errorf("Couldn't get winners response from server. id %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}

	log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %v", len(winners))

	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

// Shutdown Closes the client connection
func (c *Client) Shutdown() {
	if c.conn != nil {
		c.conn.Close()
	}
}
