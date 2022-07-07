FROM ubuntu:focal

ENV DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC

# Dependencies
RUN apt-get -y update &&\
    apt-get -y upgrade &&\
    BUILD_DEPS="\
        sudo \
        git \
        build-essential \
        pkg-config \
        python3-minimal \
        libboost-all-dev \
        libssl-dev \
        libsqlite3-dev \
        libpcap-dev \
        libsystemd-dev \
        ca-certificates \
    " &&\
    RUNTIME_DEPS=" \
        libboost-system1.71.0 \
        libboost-filesystem1.71.0 \
        libboost-date-time1.71.0 \
        libboost-iostreams1.71.0 \
        libboost-regex1.71.0 \
        libboost-program-options1.71.0 \
        libboost-chrono1.71.0 \
        libboost-random1.71.0 \
        libboost-thread1.71.0 \
        libboost-log1.71.0 \
        libboost-stacktrace1.71.0 \
        libpcap0.8 \
    " &&\
    apt-get -y install --no-install-recommends \
        $BUILD_DEPS $RUNTIME_DEPS
# ndn-cxx
RUN git clone -b ndn-cxx-0.8.0 \
    --depth=1 https://github.com/named-data/ndn-cxx.git &&\
    cd ndn-cxx &&\
    ./waf configure --with-examples &&\
    ./waf &&\
    ./waf install &&\
    cd .. && rm -r ndn-cxx
# NFD
RUN git clone -b NFD-22.02 \
    --depth=1 --recursive https://github.com/named-data/NFD.git &&\
    cd NFD &&\
    ./waf configure &&\
    ./waf &&\
    ./waf install &&\
    cp /usr/local/etc/ndn/nfd.conf.sample /usr/local/etc/ndn/nfd.conf &&\
    cd .. && rm -r NFD
# NDN tools
RUN git clone -b ndn-tools-22.02 \
    --depth=1 https://github.com/named-data/ndn-tools.git &&\
    cd ndn-tools &&\
    ./waf configure &&\
    ./waf &&\
    ./waf install &&\
    cd .. && rm -r ndn-tools
# Clean up
RUN apt-get remove --purge -y $BUILD_DEPS &&\
    apt-get remove -y .*-dev &&\
    apt-get autoremove -y &&\
    rm -rf /var/lib/apt/lists /tmp/*

ENTRYPOINT nfd

