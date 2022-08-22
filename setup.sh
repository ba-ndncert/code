#!/bin/bash

# Import .env file
if [ -f .env ]
then
  export $(cat .env | xargs)
fi

BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Setup local keychain for ndncert-server${NC}"
docker exec ndncert-server ./setup.sh

echo -e "${BLUE}Setup NDN connection to ndncert-server in ndncert-client${NC}"
docker exec ndncert-client ./setup.sh

echo -e "${BLUE}Create ca.conf for ndncert-server${NC}"
docker exec ndncert-server bin/bash -c "echo '{
    \"ca-prefix\": \"${CA_PREFIX}\",
    \"ca-info\": \"${CA_INFO}\",
    \"max-validity-period\": \"129600\",
    \"max-suffix-length\": \"2\",
    \"probe-parameters\": 
    [
        {\"probe-parameter-key\": \"email\"},
        {\"probe-parameter-key\": \"name\"}
    ],
    \"supported-challenges\":
    [
        {\"challenge\": \"pin\"},
        {\"challenge\": \"vc\"}
    ],
    \"name-assignment\":
    {
        \"param\": \"/name/email\"
    }
}' > ca.conf"
docker exec ndncert-server cat ca.conf

echo -e "${BLUE}Create client.conf for ndncert-client${NC}"
CA_CERTIFICATE=$(docker exec ndncert-server cat ${CA_PREFIX}-trust-anchor.cert)
CA_CERTIFICATE=${CA_CERTIFICATE//$'\n'/}
docker exec ndncert-client bin/bash -c "echo '{
    \"ca-list\":
    [
        {
            \"ca-prefix\": \"${CA_PREFIX}\",
            \"ca-info\": \"${CA_INFO}\",
            \"probe\": [\"email\", \"name\"],
            \"certificate\": \"${CA_CERTIFICATE}\"
        }
    ]
}' > client.conf"
docker exec ndncert-client cat client.conf

echo -e "${BLUE}Run ndncert-ca-server${NC}"
docker exec -d ndncert-server ndncert-ca-server -c ca.conf