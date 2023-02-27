"""Bot entrypoint"""

import argparse
import logging
from app import App


def get_argparser() -> argparse.ArgumentParser:
    """Setup parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-id', required=True, help='Your tg app id')
    parser.add_argument('--api-hash', required=True, help='Your tg app hash')
    parser.add_argument('--channel-file', required=True, help='File with channels to get info from')
    parser.add_argument('--log-file', default='app.log', help='Log file')
    parser.add_argument('--session-name', default='anon', help='Client session name')
    parser.add_argument('--main-channel', default='Tesytesytesy',
                        help='Channel to post downloaded media')
    return parser

def setup_logging(filename: str) -> None:
    """Setup basic logger parameters
        :param: filename - logger output file
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=filename)

def main() -> None:
    """program entrypoint"""
    parser = get_argparser()
    args, unknown = parser.parse_known_args()

    setup_logging(args.log_file)
    logger = logging.getLogger('Main')
    logger.addHandler(logging.FileHandler(args.log_file))
    logger.addHandler(logging.StreamHandler())
    logger.debug('Started with args: %s, also unknown args: %s', args, unknown)

    App(args.api_id, args.api_hash, args.main_channel, args.channel_file, args.session_name).start()

if __name__ == '__main__':
    main()
