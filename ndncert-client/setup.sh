#!/bin/bash
nfdc face create remote udp4://${SERVER_IP}
faceentry=$(nfdc face list remote udp4://$SERVER_IP)
[[ $faceentry =~ faceid=([0-9]*) ]]
faceid=$(echo ${BASH_REMATCH[1]})
nfdc route add prefix $CA_PREFIX nexthop $faceid