FROM nfd

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
    git reset --hard  e78fd4d972d0b34711896086ae5eab848b1f2595 &&\
    ./waf configure &&\
    ./waf &&\
    ./waf install