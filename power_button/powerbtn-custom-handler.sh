#!/bin/sh
SHOW_LOCK_FILE=/etc/cuems/show.lock
SERVICE_FILE=/etc/avahi/services/cuems.service
FIRST_RUN_SERVICE_FILE=/usr/share/cuems/cuems.service.firstrun

LOGGER_BINARY=/usr/bin/logger
LOGGER_OPTIONS="-p local0.info -t CUEMS_POWER -i"
LOGGER_COMMAND="$LOGGER_BINARY $LOGGER_OPTIONS"


if test -f "$SHOW_LOCK_FILE"; then
        $LOGGER_COMMAND "$SHOW_LOCK_FILE exists SHOW RUNNING, exiting without doing anything"
        exit 1
fi

pgrep -f cuems-power-button-waiter.sh > /dev/null
retVal=$?

if [ $retVal -ne 0 ]
then
        nohup /etc/acpi/cuems-power-button-waiter.sh &
        /usr/sbin/shutdown -h +1 "Power button press, Shutting down in 1 minute"
        $LOGGER_COMMAND "Power button press, Shutting down in 1 minute"

else
        $LOGGER_COMMAND "process is running, activate reset"
        /usr/sbin/shutdown -c
        /usr/bin/wall Double power button press, restarting in auto-conf mode
        /usr/bin/rm $SERVICE_FILE
        cp $FIRST_RUN_SERVICE_FILE $SERVICE_FILE
        sleep 1
        /usr/sbin/shutdown -r now "Restarting in autoconf mode"
        $LOGGER_COMMAND "Restarting in autoconf mode"
fi