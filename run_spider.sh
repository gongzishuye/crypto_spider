#!/bin/bash

set -e

export PATH=/root/anaconda3/bin:$PATH
process_name="investing_spider.py"
PROCESS=$(ps -efww | grep ${process_name} | grep -v grep | grep -v PPID | awk '{print $2}')
for i in $PROCESS
do
    echo "Kill the process [ $i ]"
    kill -9 $i
done

DATE_TIME=$(date +'%F%H%M%S')
nohup python3 investing_spider.py 2>&1>spider_${DATE_TIME}.log &
