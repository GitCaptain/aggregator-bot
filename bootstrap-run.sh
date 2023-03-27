
function help() {
cat << EOF
    Usage: ./$(basename $0) Options...
    Options:
        --help              print this help and exit
        --secret-dir        path/to/directory with api_hash and api_id files
        --channel-file      path to file with tg channels
        --artifacts-vol     volume name for bot artifacts (default: ${ARTIFACTS_VOLUME})
        --main-channel      channel where to post messages from channels from channel-file
EOF
}

ARTIFACTS_VOLUME="artifacts"
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
        --artifacts-vol)
            ARTIFACTS_VOLUME=${2}
            shift 2
            ;;
        --main-channel)
            MAIN_CHANNEL=${2}
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

echo "> creating docker volume with name: ${ARTIFACTS_VOLUME}"
docker volume create ${ARTIFACTS_VOLUME}

echo "> start docker build"
docker build --tag app_bot:0.1 --build-arg ARTIFACT_DIR="/${ARTIFACTS_VOLUME}" .

echo "> stop previous container"
docker container rm -f tg-client-bot

echo "> run docker container"
channel_file_dir="$(dirname ${CHANNEL_FILE})"
channel_file_name="$(basename ${CHANNEL_FILE})"
docker run \
    --tty \
    --interactive \
    --network host \
    --mount source="${ARTIFACTS_VOLUME}",target="/${ARTIFACTS_VOLUME}" \
    --name tg-client-bot \
    --restart on-failure \
    -v "${channel_file_dir}":"/channel_file_dir" \
    app_bot:0.1 \
    --work-dir="/${ARTIFACTS_VOLUME}" \
    --api-id="$(cat ${SECRET_DIR}/api_id)" \
    --api-hash="$(cat ${SECRET_DIR}/api_hash)" \
    --channel-file="/channel_file_dir/${channel_file_name}" \
    --main-channel="${MAIN_CHANNEL}" \
    --session-name="anon" \
    --log-file="app.log"
