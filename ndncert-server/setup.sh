#!/bin/bash
ndnsec key-gen $SERVER_NDN_PATH
ndnsec cert-dump -i $SERVER_NDN_PATH > ${SERVER_NDN_PATH}-trust-anchor.cert
ndnsec key-gen $SERVER_NDN_APPLICATION_PATH
ndnsec sign-req $SERVER_NDN_APPLICATION_PATH  | ndnsec cert-gen -s $SERVER_NDN_PATH | ndnsec cert-install -