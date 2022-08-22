#!/bin/bash
ndnsec key-gen $CA_PREFIX
ndnsec cert-dump -i $CA_PREFIX > ${CA_PREFIX}-trust-anchor.cert