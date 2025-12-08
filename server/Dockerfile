FROM docker.io/cloudflare/sandbox:0.6.0-python

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip \
 && ln -sf /usr/bin/python3 /usr/local/bin/python3 \
 && ln -sf /usr/bin/pip3 /usr/local/bin/pip3 \
 && rm -rf /var/lib/apt/lists/*

# Required during local development to access exposed ports
EXPOSE 8080
