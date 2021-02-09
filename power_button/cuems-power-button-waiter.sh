#!/bin/sh
SLEEP_TIME=3
LOGGER_BINARY=/usr/bin/logger
LOGGER_OPTIONS="-p local0.info -t CUEMS_POWER -i"
LOGGER_COMMAND="$LOGGER_BINARY $LOGGER_OPTIONS"

LOGGER_COMMAND  "Power button pressed, waiting 10 secs for another press"
sleep $SLEEP_TIME
