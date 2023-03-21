FROM alpine:3.14

ENV USER="bot"
ENV HOME="/home/${USER}"

RUN addgroup "${USER}" && adduser \
    --disabled-password \
    --gecos "" \
    --home "${HOME}" \
    --system \
    --ingroup "${USER}" \
    "${USER}"

COPY requirements.txt "${HOME}"

RUN apk add --no-cache \
    python3=~3.9 \
    py3-pip=~20.3 \
    curl=~7.79 \
    gcc=~10.3 \
    musl-dev=~1.2.2 \
    && python3 -m pip install --upgrade pip

USER "${USER}"
WORKDIR "${HOME}"

# rust needed for python cryptg
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="${HOME}/.cargo/bin:${PATH}"

RUN python3 -m pip install -r "${HOME}/requirements.txt"

ENV PATH="${HOME}/.local/bin:${PATH}"
COPY client ${HOME}/client
ENTRYPOINT [ "python3", "client/main.py"]
