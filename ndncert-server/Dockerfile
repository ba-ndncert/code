FROM ndncert:latest

USER root

COPY producer.cpp .

RUN g++ producer.cpp -o producer -lndn-cxx -lboost_system

COPY setup.sh .
RUN chmod +x ./setup.sh

COPY ca.conf .
