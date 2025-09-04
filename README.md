# Entrega TP0 - Josue Martel - 110696

## Asunciones

- Tanto clientes como servidor se ejecutan en entornos Unix (Linux)

- Como regla de negocio, el servidor siempre atiende a $n$ agencias como máximo en paralelo. donde $n = 5$ dado el enunciado, además de configurable bajo el archivo `server/params.ini`

## Desarrollo Parte 1 - Introducción a Docker
### Ejercicio 1
Se desarrolló el script de bash `generar-compose.sh` que delega la funcionalidad de generación a un script en python `generador.py`. Se usó de referencia el esqueleto para el formato de salida del archivo generado.

### Ejercicio 2
Dado que originalmente se copian los archivos de configuración al container, se modificaron los Dockerfiles tanto de cliente como servidor. Luego se agregaron como `volumes` en el generador de compose.

### Ejercicio 3
Se definió el validador como imagen, para ser levantado como contenedor al ejecutar `validar-echo-server.sh`. 

``` bash
docker build -t validator-latest ./validator
```

Dicho validador tendrá netcat instalado y se conectará a la red `tp0_testing_net` (docker-network).
Una vez levantado ejecutará el comando nc enviando el mensaje a validar al servidor, se esperará la respuesta y se cerrará la conexión.
``` bash
RESPONSE=$(docker run --rm --network tp0_testing_net --entrypoint /bin/sh validator-latest -c "echo '$MSG' | nc -q 1 server 12345")
```
### Ejercicio 4

Para la terminación graceful ante el signal SIGTERM se implementaron los handlers correspondientes para el cierre de los sockets en cada aplicación.

**Desde el cliente**
``` go
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM)
	
	// Goroutine to handle the SIGTERM signal
	go func() {
		<-sigChan
		log.Infof("closing client socket [sigterm]")
		client.Shutdown();
		os.Exit(0) // Graceful exit on signal
	}()
```

**Desde el servidor**

``` python
    def sigterm_handler(self, signum, _):
        logging.info('closing server socket [sigterm]')
        self._server_socket.close()
        if self._client_sock:
            logging.info('closing connected client socket [sigterm]')
            self._client_sock.close()
        sys.exit(0) # Graceful exit on signal
    
    def run(self):
        ...
        # Register SIGTERM signal handler
        signal.signal(signal.SIGTERM, self.sigterm_handler)
```


## Desarrollo Parte 2 - Repaso de Comunicaciones

### Ejercicio 5

Las variables de entorno requeridas fueron establecidas con el generador de compose para los contenedores de los clientes.

Para este ejercicio se asume que cada agencia enviará la apuesta de 1 solo cliente (definido por las variables de entorno).

Para evitar los *short-writes* desde el lado del cliente, se implementó la función `WriteAll`. De forma análoga, para evitar los *short-reads* desde el lado del servidor, se implementó la función `recv_all`. Asegurando escribir y recibir una determinada cantidad de bytes respectivamente. 

Se implementó el siguiente protocolo para el envío y recepción de apuesta de una persona:

| Campo              | Tamaño  | Descripción                                         |
| ------------------ | ------- | --------------------------------------------------- |
| `n`                | 4 bytes | Longitud del nombre (entero, Big Endian)            |
| `m`                | 4 bytes | Longitud del apellido (entero, Big Endian)          |
| `d`                | 4 bytes | Longitud de la fecha de nacimiento (entero, Big Endian) |
| `nombre`           | **n** bytes | Nombre (UTF-8)                                      |
| `apellido`         | **m** bytes | Apellido (UTF-8)                                    |
| `fecha nacimiento` | **d** bytes | Fecha de nacimiento (UTF-8, `"YYYY-MM-DD"`)     |
| `dni`              | 4 bytes | DNI (entero, Big Endian)                            |
| `numero apuesta`   | 4 bytes | Número de apuesta (entero, Big Endian)              |

### Ejercicio 6

Se agregó el archivo .csv correspondiente a cada agencia con docker-volumes mediante el generador de compose.

A diferencia del ejercicio anterior, ahora se espera recibir varias apuestas en batch por conexión de agencia al servidor. Adaptando a esta situación al protocolo, se agregó el envío de cantidad de apuestas en el batch previo al envío de cada apuesta.

| Campo              | Tamaño  | Descripción                                         |
| ------------------ | ------- | --------------------------------------------------- |
| `id`                | 4 bytes | Id de la agencia (entero, Big Endian)            |
| `n`      | 4 bytes | Cantidad de apuestas en el batch (entero, Big Endian)          |

De esta forma el servidor sabe cuántas apuestas espera recibir antes de cerrar la conexión con el cliente.

Para respetar la restricción de 8KB por batch enviado (configurable en `client/params.yaml`), al leer cada apuesta se calcula y suma el tamaño de paquete que ocuparía al enviarse (en bytes), si no se sobrepasa el límite, se almacena la apuesta en lista. Finalizada la lectura (por `EOF` o `batch maxAmount`) se procede a enviar la cantidad de apuestas del batch seguido de las mismas.

``` go

	bytesToSend := 0
	var betsBatch []Bet
	for	 i := 0; i < c.config.BatchMax; i++ {
		record, err := reader.Read()
		// ...
		bet, err := ReadBet(record)
		// ...
		// Hard limit for Batch size (8KB)
		if bytesToSend + GetBetPacketSize(bet) > c.params.MaxBatchSize {
			log.Errorf("Invalid batch size, skipping")
			c.conn.Close()
			return
		}
		betsBatch = append(betsBatch, bet)
		bytesToSend += GetBetPacketSize(bet)
	}
	err := SendBatchCount(c.conn, agency_id, len(betsBatch)); 
	// ...
	for _, bet := range betsBatch {	
		err := SendBet(c.conn, bet)
		// ...
	}
	c.conn.Close()


```

### Ejercicio 7

En este ejercicio el cliente debe poder recibir la lista de ganadores. Para evitar los *short-reads* desde el lado del cliente, se implementó la función `ReadAll`.

Si bien se sigue enviando la cantidad de apuestas en cada batch que se envía al servidor, ahora es necesario avisarle cuándo dejar de esperar recibir más. Para esto se adapta el protocolo al enviar la cantidad de apuestas por batch, agregando un flag que representa si dicho batch es el último enviado por el cliente.

| Campo              | Tamaño  | Descripción                                         |
| ------------------ | ------- | --------------------------------------------------- |
| `id`                | 4 bytes | Id de la agencia (entero, Big Endian)            |
| `n`      | 4 bytes | Cantidad de apuestas en el batch (entero, Big Endian)          |
| **`último`**      | **1 byte** | **Flag encendido si el batch es el último de la agencia (booleano, comprimido)**          |

Cuando el cliente envía el flag encendido, procederá a esperar la respuesta de sus ganadores.

En el lado servidor, al recibir el flag encendido de todos los clientes registrados, se procede al envío de ganadores de los mismos.

Para dicho envío, se acopla al protocolo el envío de ganadores para cada agencia.

| Campo              | Tamaño  | Descripción                                         |
| ------------------ | ------- | --------------------------------------------------- |
| `n`      | 4 bytes | Cantidad de ganadores a recibir (entero, Big Endian)          |
...
| `dni i`      | 4 bytes | DNI del ganador $i$ de la agencia (entero, Big Endian)          |       
... 
Hasta **n**

## Desarrollo Parte 3 - Repaso de Concurrencia

### Ejercicio 8
Se modeló la concurrencia basada en procesos, utilizando el módulo ``multiprocessing`` de python (aprobado por la cátedra).

Si bien para este tp las limitaciones del lenguaje con threads no son un problema dados los únicos 5 clientes a atender. Se eligió este modelo por la escalabilidad que provee tanto para el manejo de clientes en simultáneo como el procesamiento de batches.

Definida la cantidad máxima de agencias a soportar (5 dado el enunciado y configurable en `server/params.ini`) se estableció un pool de procesos (client workers) los cuáles se encargarán de atender a cada cliente. Teniendo 5 + 1 worker que esperará hasta que todos los clientes hayan enviado sus apuestas (lo llamaremos Ending worker). Dejando así al proceso principal encargarse únicamente de la aceptación de clientes.

Para la protección de recursos y sección crítica se usó una "Conditional Variable (Lock asociado)" la cual opera sobre el Ending worker, siendo notificado cuando un cliente persiste el batch enviado.

**Clients workers**
``` python
    def _handle_client_connection(self, client_sock):
            # ...
            with self._cond:
                store_bets(bets_in_batch)                
                self._agencies[agency_id] = True

                if is_last_batch:
                    self._clients_done_sockets[agency_id] = client_sock
                else:
                    client_sock.close()

                self._cond.notify_all()
            # ...

```

**Ending worker**
``` python
   def _wait_for_input_ending(self):
        with self._cond:
            agencies_alive_result = self._cond.wait_for(
                lambda: len(self._agencies) == self._max_agencies, 
                timeout=self._agency_connection_timeout
                )
            # ...
            while len(self._clients_done_sockets) < len(self._agencies):
                self._cond.wait() # Waiting for all conected agencies to finish

            self._send_winners()
```

El timeout de espera de registro de agencias es también configurable desde `server/params.ini`

NOTA: Siendo este el último ejercicio, se agregó además resilencia por parte del cliente, teniendo una cantidad de intentos de conexión al servidor configurable desde `client/params.yaml`

## Ejecución
El repositorio cuenta con un **Makefile** que incluye distintos comandos en forma de targets. Los targets se ejecutan mediante la invocación de:  **make \<target\>**. Los target imprescindibles para iniciar y detener el sistema son **docker-compose-up** y **docker-compose-down**, siendo los restantes targets de utilidad para el proceso de depuración.

Los targets disponibles son:

| target  | accion  |
|---|---|
|  `docker-compose-up`  | Inicializa el ambiente de desarrollo. Construye las imágenes del cliente y el servidor, inicializa los recursos a utilizar (volúmenes, redes, etc) e inicia los propios containers. |
| `docker-compose-down`  | Ejecuta `docker-compose stop` para detener los containers asociados al compose y luego  `docker-compose down` para destruir todos los recursos asociados al proyecto que fueron inicializados. Se recomienda ejecutar este comando al finalizar cada ejecución para evitar que el disco de la máquina host se llene de versiones de desarrollo y recursos sin liberar. |
|  `docker-compose-logs` | Permite ver los logs actuales del proyecto. Acompañar con `grep` para lograr ver mensajes de una aplicación específica dentro del compose. |
| `docker-image`  | Construye las imágenes a ser utilizadas tanto en el servidor como en el cliente. Este target es utilizado por **docker-compose-up**, por lo cual se lo puede utilizar para probar nuevos cambios en las imágenes antes de arrancar el proyecto. |
| `build` | Compila la aplicación cliente para ejecución en el _host_ en lugar de en Docker. De este modo la compilación es mucho más veloz, pero requiere contar con todo el entorno de Golang y Python instalados en la máquina _host_. |


