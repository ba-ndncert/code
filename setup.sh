#!/bin/bash

BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Setup local keychain for ndncert-server${NC}"
docker exec ndncert-server ./setup.sh

echo -e "${BLUE}Setup NDN connection to ndncert-server in ndncert-client${NC}"
docker exec ndncert-client ./setup.sh

echo -e "${BLUE}Run ndncert-ca-server${NC}"
docker exec -d ndncert-server ndncert-ca-server -c ca.conf