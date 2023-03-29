FROM alpine:3.14

ARG ARTIFACT_DIR

COPY requirements.txt /tmp

RUN apk add --no-cache \
    python3=~3.9 \
    py3-pip=~20.3 \
    curl=~7.79 \
    gcc=~10.3 \
    musl-dev=~1.2.2 \
    && python3 -m pip install --upgrade pip

# rust needed for python cryptg
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

USER root
ENV HOME=/root
ENV PATH="${HOME}/.cargo/bin:${PATH}"
RUN python3 -m pip install -r "/tmp/requirements.txt"
COPY client /root/client

WORKDIR ${HOME}
ENTRYPOINT ["python3", "client/main.py"]
