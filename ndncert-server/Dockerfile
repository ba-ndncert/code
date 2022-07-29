FROM ndncert

USER root

ENV SERVER_NDN_PATH=/example
ENV SERVER_NDN_APPLICATION_PATH=/example/testApp

COPY producer.cpp .

RUN g++ producer.cpp -o producer -lndn-cxx -lboost_system

COPY setup.sh .
RUN chmod +x ./setup.sh

COPY ca.conf .