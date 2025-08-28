#!/bin/bash

MSG="hola-echo"

docker build -t validator-latest ./validator

RESPONSE=$(docker run --rm --network tp0_testing_net --entrypoint /bin/sh validator-latest -c "echo '$MSG' | nc server 12345")

if [ "$RESPONSE" = "$MSG" ]; then
  echo "action: test_echo_server | result: success"
else
  echo "action: test_echo_server | result: fail"
fi
