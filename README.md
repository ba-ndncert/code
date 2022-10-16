1. Quick start was tested on a Ubuntu 20.04.4 LTS host system.
1. Install Python3.9, pip and git
    ```
    sudo apt install python3.9
    sudo apt install python3-pip
    sudo apt install git
    ```
1. Install Docker Compose and Docker Engine v2.0 https://docs.docker.com/engine/install/ubuntu/.
1. Clone the following Git repositories:
    ```
    git clone https://github.com/ba-ndncert/code
    git clone https://github.com/bcgov/von-network
    ```
1. Open `./von-network/manage` and replace `docker-compose` with `docker compose` in lines 21 and 22.
1. In `./von-network` run: 
    ```
    ./manage build
    ./manage start
    ```
1. In `./code/.env` replace `LEDGER_URL` with the host's IP address at port 9000.
1. In `./code` run:
    ```
    ./setup_ledger
    docker build -t nfd:latest ./nfd
    docker build -t ndncert:latest ./ndncert
    docker compose up
    ```
    This will start the Docker containers defined in `./code/docker-compose.yml`.
1.  In `./code` run:
    ```
    ./setup_ndncert
    ```
    This will perform the setup for the containers `ndncert-server` and `ndncert-client`.
1. In `./code` run:
    ```
    python3.9 -m pip install -r ./controller_pkg/requirements.txt
    python3.9 ./controller_pkg/setup.py --env_path ./.env
    ```
    This will perform the setup for the containers `server-agent` and `client-agent`.
1. In `./code` run:
    ```
    docker exec -it ndncert-client ndncert-client -c client.conf
    ```
