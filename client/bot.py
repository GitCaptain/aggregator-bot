import logging
import telethon


class Bot:

    def __init__(self, client: telethon.TelegramClient) -> None:
        self.client = client
        self.logger = logging.getLogger('Main.bot')

    async def start(self) -> None:
        self.logger.info('bot started')
        me = self.client.get_me()
        dialogs = self.client.iter_dialogs()
        self.logger.debug('me: %s', (await me).stringify())
        async for dialog in dialogs:
            if dialog.is_channel or dialog.is_group:
                self.logger.debug('dialog: %s', dialog.stringify())