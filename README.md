## Simple tg bot (client) which monitors choosen channels and copy info from
them to another place.


### Dev

To bootstrap developer environment run `./bootstrap-dev.sh` from the project
root. This script will set virtual python environment, install required packages
and set git hooks.
Note: you can also pass `--build-arg dev-build=x` to docker build command, so it
will install developer packages inside the container, you can then do your work
inside it.

### Usage

To use this bot you should get api_hash and api_id for your app here:
https://my.telegram.org/apps
You should also have docker installed.

You need to create file with channels username which you want to get posts from.
e.g. channelfile:

```
username1
username2
username3
# username4 - will be ignored
username5
....
```

To start app you need to run `bootstrap-run.sh` script with info from previous
steps:
```
echo your_api_id > SECRET_DIR/api_id
echo your_api_hash > SECRET_DIR/api_hash
./bootstrap.sh --secret-dir /path/to/SECRET_DIR \
               --channel-file path/to/channelfile \
               --main-channel your_tg_channel
```

<b> Please, note: on the first run (e.g. you do not have session file yet) you
will have to login into your telegramm account </b>
