FROM ndncert:latest

USER root

COPY consumer.cpp .

RUN g++ consumer.cpp -o consumer -lndn-cxx -lboost_system

COPY trust-schema.conf .

COPY setup.sh .
RUN chmod +x ./setup.sh

COPY client.conf .
