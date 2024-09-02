FROM alpine:3.20

COPY requirements*.txt /tmp

# Do not override from CLI - this is the set of packages that needed only during
# the build process, will be removed at the end.
ARG __BUILD_TIME_PKGS="\
python3-dev=~3.12 \
py3-pip=~24.0 \
gcc=~13.2 \
musl-dev=~1.2.5 \
libjpeg-turbo-dev=~3.0 \
zlib-dev=~1.3 \
"

ARG user=bot
ARG uid=501
ENV HOME="/home/${user}"

# 1. Install required packages
# 2. Add user to run app
RUN apk add --no-cache \
    python3=~3.12 \
    ${__BUILD_TIME_PKGS} && \
    adduser -h "${HOME}" -D -u ${uid} ${user}

USER ${user}
# rust needed for python cryptg
RUN wget -O - https://sh.rustup.rs | sh -s -- -y
ENV PATH="${HOME}/.cargo/bin:${PATH}"

# if non-empty - dev requirements will be installed
ARG dev-build=""

# I don't think these packages can break something on clean alpine system in
# docker, and venv in container seems to be overkill, so use
# `break-system-packages` flag to avoid `externally-managed-environment Error`.
RUN if [ -n ${dev-build} ]; then suffix="-dev"; fi; \
    python3 -m pip install --break-system-packages \
            -r "/tmp/requirements${suffix}.txt"

USER root
# 1. Remove requirements files
# 2. Remove versions from build time packages and remove packages from system
RUN rm /tmp/requirements*.txt && \
    apk del $(echo "${__BUILD_TIME_PKGS}" | sed 's/=[^ ]*//g')

USER "${user}"

# copy client code each time version changed
ARG VERSION=0.1
COPY client ${HOME}/client

WORKDIR ${HOME}
ENTRYPOINT ["python3", "client/main.py"]
