#!/bin/bash

# check if container is running
if docker ps -q --filter "name=ptsb-checkbot" | grep -q .; then
    echo "Stopping container ptsb-checkbot..."
    docker stop ptsb-checkbot
else
    echo "Container ptsb-checkbot is not running. Going forward..."
fi

echo " "

# checking if container exists
if docker ps -a -q --filter "name=ptsb-checkbot" | grep -q .; then
    echo "Deleting container ptsb-checkbot..."
    docker rm ptsb-checkbot
else
    echo "Container ptsb-checkbot was not found. Going forward..."
fi

echo " "

# checking if image exists
if docker images --filter "reference=builder-ptsb-checkbot" -q | grep -q .; then
    echo "Deleting image builder-ptsb-checkbot..."
    docker rmi builder-ptsb-checkbot
else
    echo "Image builder-ptsb-checkbot was not found."
fi

echo " "

echo "Application ptsb-checkbot was fully removed from sysytem."