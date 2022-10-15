FROM nfd:latest

USER root

RUN apt-get -y update &&\
    apt-get -y upgrade &&\
    BUILD_DEPS="\
        build-essential \
        libsqlite3-dev \
        libssl-dev \
        libboost-all-dev \
    " &&\
    apt-get -y install --no-install-recommends \
        $BUILD_DEPS

RUN git clone https://github.com/DavidBarke/ndncert.git

RUN cd /ndncert &&\
    ./waf configure &&\
    ./waf &&\
    ./waf install

RUN ldconfig
