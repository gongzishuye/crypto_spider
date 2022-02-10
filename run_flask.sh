#!/bin/bash

set -e

export PATH=/root/anaconda3/bin:$PATH
process_name="coin_signal_server.py"
PROCESS=$(ps -efww | grep ${process_name} | grep -v grep | grep -v PPID | awk '{print $2}')
for i in $PROCESS
do
    echo "Kill the process [ $i ]"
    kill -9 $i
done

DATE=$(date +'%F%H%M%S')
nohup python3 coin_signal_server.py 2>&1 > flask_$DATE.log &
