import email
from logger import configure_logging
from imapclient import IMAPClient
from subprocess import run, PIPE, CalledProcessError
from config import settings

logger = configure_logging()
rspamc_error_folder = '{}rspamc_error'.format(settings.inbox_prefix)
decoding_error_folder = '{}decoding_error'.format(settings.inbox_prefix)
charsets = [
    'iso-8859-1', # latin_1
    'utf-8',
    'us-ascii',
    'iso-8859-2',
    'cp1252'
]

def move_to_folder(server: object, uid: int, folder: str):
    if not server.folder_exists(folder):
        server.create_folder(folder)
        server.subscribe_folder(folder)
    server.move([uid], folder)

with IMAPClient(settings.host, ssl=True) as server:
    server.login(settings.username, settings.password)
    for suffix in settings.folder_suffixes:
        report_folder = '{}report_{}'.format(settings.inbox_prefix, suffix)
        learned_folder = '{}learned_{}'.format(settings.inbox_prefix, suffix)
        rspamc_command = 'learn_spam' if suffix == 'spam' else 'learn_ham'

        server.select_folder(report_folder, readonly=False)
        messages = server.search('ALL')
        for uid, message_data in server.fetch(messages, 'RFC822').items():
            raw_message = message_data[b'RFC822']
            msg = email.message_from_bytes(raw_message)

            msg_id = msg.get('Message-ID')
            logger.info('{}:{} From:{} To:{} Message-ID: {}'.format(report_folder, uid, msg.get('From'), msg.get('To'), msg_id))
            logger.info('running rspamc {} ...'.format(rspamc_command))

            charsets.insert(0, msg.get_content_charset('utf-8'))
            success = False
            for charset in charsets:
                try:
                    message_decoded = raw_message.decode(charset)
                    message_charset = charset
                    success = True
                    break
                except UnicodeDecodeError as e:
                    logger.info('decoding error (Message-ID: {}): {}'.format(msg_id, e))
                except LookupError as e:
                    logger.info(e)
            if not success:
                move_to_folder(server, uid, decoding_error_folder)
                logger.warning('not able to decode message (Message-ID: {}), email was moved to {}'.format(msg_id, decoding_error_folder))
                continue

            p = run(['/usr/bin/rspamc', rspamc_command], stdout=PIPE, input=message_decoded, encoding=message_charset)
            try:
                p.check_returncode() # If returncode is non-zero, raise a CalledProcessError.
                logger.info('rspamc output:\n{}'.format(p.stdout.rstrip()))
                move_to_folder(server, uid, learned_folder)
            except CalledProcessError as e:
                if 'all learn conditions denied learning' in e.output:
                    logger.warning('rspamc {} failed on email with Message-ID: {}'.format(rspamc_command, msg_id))
                    logger.warning('rspamc error ({}): {}'.format(p.returncode, e.output))
                    move_to_folder(server, uid, learned_folder)
                else:
                    logger.error('rspamc {} failed on email with Message-ID: {}'.format(rspamc_command, msg_id))
                    logger.error('rspamc error ({}): {}'.format(p.returncode, e.output))
                    move_to_folder(server, uid, rspamc_error_folder)
                    logger.error('email was moved to {}'.format(rspamc_error_folder))
