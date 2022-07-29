FROM ndncert

USER root

ENV SERVER_IP=10.0.0.2
ENV SERVER_NDN_PATH=/example

COPY consumer.cpp .

RUN g++ consumer.cpp -o consumer -lndn-cxx -lboost_system

COPY trust-schema.conf .

COPY setup.sh .
RUN chmod +x ./setup.sh

COPY client.conf .