package common

import (
	"net"
	"time"
	"github.com/op/go-logging"
	"os"
    "strconv"
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
	MaxBatchSize		  int
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
	config 	  ClientConfig
	params 	  ClientParams
	conn   	  net.Conn
	dataset   *os.File
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
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
	}
	c.conn = conn
	return err
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
	c.dataset = f
	defer c.dataset.Close()
	reader := csv.NewReader(c.dataset)
	
	done := false
	for !done {

		if err := c.createClientSocket(); err != nil {
			log.Errorf("Couldn't connect to server. id %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}

		bytesToSend := 0

		var betsBatch []Bet

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

			// Hard limit for Batch size (8KB)
			if bytesToSend + GetBetPacketSize(bet) > c.params.MaxBatchSize {
				log.Errorf("Invalid batch size, skipping")
				c.conn.Close()
				return
			}

			betsBatch = append(betsBatch, bet)
			bytesToSend += GetBetPacketSize(bet)
		}

		if err := SendBatchCount(c.conn, agency_id, len(betsBatch), done); err != nil {
			log.Errorf("Couldn't send end batch count to server. id %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}

		for _, bet := range betsBatch {	
			err := SendBet(c.conn, bet)
			
			if err != nil {
				log.Errorf("Couldn't send bet to server. id %v | error: %v",
					c.config.ID,
					err,
				)
				break
			}

			log.Infof("action: apuesta_enviada | result: success | dni: %v | numero: %v", bet.dni, bet.number)
		}

		if !done{
			c.conn.Close()
			time.Sleep(c.config.LoopPeriod)
		}
	}
	
	// Wait for the winner response
	winners, err := GetWinnersResponse(c.conn)
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
		c.conn = nil
	}
	if c.dataset != nil {
		c.dataset.Close()
		c.dataset = nil
	}
}
