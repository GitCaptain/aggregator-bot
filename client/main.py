"""Bot entrypoint"""

import argparse
import logging
import os

from app import App


def get_argparser() -> argparse.ArgumentParser:
    """Setup parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-id', required=True, help='Your tg app id')
    parser.add_argument('--api-hash', required=True, help='Your tg app hash')
    parser.add_argument('--channel-file', required=True, help='File with channels to get info from')
    parser.add_argument('--log-file', default='app.log', help='Log file')
    parser.add_argument('--session-name', default='anon', help='Client session name')
    parser.add_argument('--main-channel', required=True, help='Channel to post downloaded media')
    parser.add_argument('--work-dir', default=os.path.join(os.path.curdir, 'app_work'),
                        help='Directory with bot artifacts')
    return parser

def setup_logging(logger: logging.Logger, filepath: str) -> None:
    """Setup logger handlers"""

    # TODO: add handler to send error to user
    fh = logging.FileHandler(filepath)
    dbg_fh = logging.FileHandler(f'{filepath}.full')
    sh = logging.StreamHandler()

    fh.setLevel(logging.INFO)
    dbg_fh.setLevel(logging.DEBUG)
    sh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s: %(message)s')
    dbg_formatter = logging.Formatter(
                            '%(asctime)s - %(levelname)s - %(module)s - %(funcName)s: %(message)s')
    fh.setFormatter(formatter)
    dbg_fh.setFormatter(dbg_formatter)
    sh.setFormatter(formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=[fh, sh])

    # set app logger
    logger.addHandler(dbg_fh)

    # set telethon logger
    telethonlog = logging.getLogger('telethon')
    telethon_hndl = logging.FileHandler(f'{filepath}.telethon.full')
    telethon_hndl.setLevel(logging.DEBUG)
    telethon_hndl.setFormatter(dbg_formatter)
    telethonlog.addHandler(telethon_hndl)

def main() -> None:
    """program entrypoint"""
    parser = get_argparser()
    args, unknown = parser.parse_known_args()

    logger = logging.getLogger('Main')
    setup_logging(logger, os.path.join(args.work_dir, args.log_file))
    logger.info('Started with args: %s, also unknown args: %s', args, unknown)
    App(args.api_id, args.api_hash, args.work_dir) \
        .start(args.session_name, args.main_channel, args.channel_file)

if __name__ == '__main__':
    main()
