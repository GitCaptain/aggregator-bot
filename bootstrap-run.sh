#!/usr/bin/env bash

set -eu

function help() {
cat << EOF
Usage: ./$(basename $0) Options...
Options:
    --help              Print this help and exit
    --secret-dir        Path/to/directory with api_hash and api_id files
    --channel-file      Path to file with tg channels
    --main-channel      Channel where to post messages from channels from channel-file
    --container-name    Container name to run (default: ${CONTAINER_NAME})
    --image-tag         Image tag to pull from docker hub (default: ${IMAGE_TAG})
    --rebuild           Do not pull container, force rebuild it.
EOF
}

CONTAINER_NAME="app_bot"
IMAGE_TAG="latest"
while (($#)); do
    case $1 in
        --help)
            help
            exit 0
            ;;
        --secret-dir)
            SECRET_DIR=${2}
            shift 2
            ;;
        --channel-file)
            CHANNEL_FILE=${2}
            shift 2
            ;;
        --main-channel)
            MAIN_CHANNEL=${2}
            shift 2
            ;;
        --image-tag)
            IMAGE_TAG=${2}
            shift 2
            ;;
        --rebuild)
            REBUILD=1;
            shift
            ;;
        --container-name)
            CONTAINER_NAME=${2};
            shift 2
            ;;
        *)
            help
            exit 1
            ;;
    esac
done

[[ -z ${SECRET_DIR} || -z ${CHANNEL_FILE} || -z ${MAIN_CHANNEL} ]] && \
    echo "> Secret dir, channel file ot main channel are not provided" && exit 1

if ! ((REBUILD)); then
    echo "> trying to pull docker container"
    docker pull justgivemeregisterplease/app_bot:${IMAGE_TAG} || cant_pull=1
fi

if ((REBUILD)) || ((cant_pull)); then
    echo "> can't pull container"
    echo "> start docker build"
    docker build --tag ${CONTAINER_NAME}:${IMAGE_TAG} .
fi

echo "> stop previous container"
docker container rm -f tg-client-bot

echo "> run docker container"
channel_file_dir="$(dirname ${CHANNEL_FILE})"
channel_file_name="$(basename ${CHANNEL_FILE})"
(set -x; docker run \
    --tty \
    --interactive \
    --detach \
    --network host \
    --name tg-client-bot \
    --restart always \
    -v "${channel_file_dir}":"/channel_file_dir" \
    ${CONTAINER_NAME}:${IMAGE_TAG} \
    python3 client/main.py \
        --work-dir="/home/bot" \
        --api-id="$(cat ${SECRET_DIR}/api_id)" \
        --api-hash="$(cat ${SECRET_DIR}/api_hash)" \
        --channel-file="/channel_file_dir/${channel_file_name}" \
        --main-channel="${MAIN_CHANNEL}" \
        --session-name="bot" \
        --log-file="app.log" )
