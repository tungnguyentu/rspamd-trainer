# rspamd-trainer

## Install

### Install rspamd-trainer

Install `rspamd-trainer` with Python 3 venv:

```bash
$ git clone https://github.com/tungnguyentu/rspamd-trainer.git
$ cd rspamd-trainer
$ python3 -m venv venv
$ . venv/bin/activate
(venv) $ pip install -r requirements.txt
```

### Configure

Configuration is stored in `.env`. See `.env.example` for default config options.

```ini
HOST=localhost
USERNAME=spam@example.com
PASSWORD=xxxxxxxxxxxxxxxx
INBOX_PREFIX=INBOX/
```

### Setup spam learning mailaccount

Create the mailaccount for spam learning, e.g. spam@example.com (put credentials in `.env`) with at least the following folders:

- `INBOX/report_spam`
- `INBOX/report_ham`
- `INBOX/report_spam_reply`

The `INBOX/learned_*` folders will be created by rspamd-trainer upon first moved emails, if they don't exist.

## Development

### Initialize environment

Create venv and install new packages:

```bash
$ python3 -m venv venv
$ . venv/bin/activate
(venv) $ pip install -r requirements.txt
```

## Usage

### Cronjob

Run rspamd-trainer on a regular basis, e.g. every 5mins via cronjob:

```
*/5 * * * * root /opt/rspamd-trainer/venv/bin/python run.py
```

### Dovecot / IMAPSieve

For **automated spam/ham learning** via Dovecot/IMAPSieve
This does the following:

- Copy an email to the `report_spam` mailbox (to be learned by rspamd-trainer as **spam**,  `rspamc learn_spam`) if any user copies it from elsewhere to his `Spam` folder or if a flag is changed on an email in `Spam` folder.
- Copy an email to the `report_spam_reply` mailbox (to be learned by rspamd-trainer as **ham**, `rspamc learn_ham`) if any user replies to or forwards a message from the `Spam` folder
- Copy an email to the `report_ham` mailbox (to be learned by rspamd-trainer as **ham**, `rspamc learn_ham`) if any user copies it from his `Spam` folder to elsewhere.

Spam/Ham learning is triggered via Dovecot/IMAPSieve configuration in `conf.d/90-sieve.conf`:

```ini
plugin {
  ###
  ### Spam learning with IMAPSieve
  ### see https://rspamd.com/doc/tutorials/feedback_from_users_with_IMAPSieve.html
  ### Note: MUAs may move message with COPY or APPEND (MS Outlook) (IMAP) command.
  ###
  # Spam: From elsewhere to Spam folder or flag changed in Spam folder
  imapsieve_mailbox1_name = INBOX/Spam
  imapsieve_mailbox1_causes = COPY APPEND FLAG
  imapsieve_mailbox1_before = file:/var/lib/dovecot/sieve/learn-spam.sieve

  # Ham: From Spam folder to elsewhere
  imapsieve_mailbox2_name = *
  imapsieve_mailbox2_from = INBOX/Spam
  imapsieve_mailbox2_causes = COPY
  imapsieve_mailbox2_before = file:/var/lib/dovecot/sieve/learn-ham.sieve
}
```

Global `learn-spam.sieve`:

```sieve
require ["vnd.dovecot.pipe", "copy", "imapsieve", "environment", "imap4flags", "vnd.dovecot.debug", "variables"];

# Logging
if address :matches "from" "*" { set "FROM" "${1}"; }
if address :matches "to" "*" { set "TO" "${1}"; }
if header :matches "subject" "*" { set "SUBJECT" "${1}"; }
if header :matches "Message-ID" "*" { set "MSGID" "${1}"; }
if header :matches "X-Spamd-Result" "*" { set "XSpamdResult" "${1}"; }
if environment :matches "imap.cause" "*" { set "IMAPCAUSE" "${1}"; }
debug_log "learn-spam.sieve was triggered on imap.cause=${IMAPCAUSE}: msgid=${MSGID}";
set "LogMsg" "learn-spam on imap.cause=${IMAPCAUSE}: from=${FROM}, to=${TO}, subject=${SUBJECT}, msgid=${MSGID}, X-Spamd-Result=${XSpamdResult}";

# Spam-learning by storing a copy of the message into spam@example.com
if anyof (environment :is "imap.cause" "COPY", environment :is "imap.cause" "APPEND") {
    debug_log "${LogMsg}";
    debug_log "learn-spam copy to INBOX/report_spam";
    pipe :copy "dovecot-lda" [ "-d", "spam@example.com", "-m", "INBOX/report_spam" ];
}
# Catch replied or forwarded spam (to be learned as ham)
elsif anyof (allof (hasflag "\\Answered", environment :contains "imap.changedflags" "\\Answered"),
             allof (hasflag "$Forwarded", environment :contains "imap.changedflags" "$Forwarded")) {
    debug_log "${LogMsg}";
    debug_log "learn-ham copy to INBOX/report_spam_reply";
    pipe :copy "dovecot-lda" [ "-d", "spam@example.com", "-m", "INBOX/report_spam_reply" ];
}
```

Global `learn-ham.sieve`:

```sieve
require ["vnd.dovecot.pipe", "copy", "imapsieve", "environment", "variables", "vnd.dovecot.debug"];

# Exclude messages which were moved to Trash (or training mailboxes) from ham learning
if environment :matches "imap.mailbox" "*" {
    set "mailbox" "${1}";
}
if string "${mailbox}" [ "INBOX/Trash", "INBOX/Deleted Items", "INBOX/Bin", "INBOX/train_ham", "INBOX/train_prob", "INBOX/train_spam" ] {
    stop;
}

# Logging
if address :matches "from" "*" { set "FROM" "${1}"; }
if address :matches "to" "*" { set "TO" "${1}"; }
if header :matches "subject" "*" { set "SUBJECT" "${1}"; }
if header :matches "Message-ID" "*" { set "MSGID" "${1}"; }
if header :matches "X-Spamd-Result" "*" { set "XSpamdResult" "${1}"; }
if environment :matches "imap.cause" "*" { set "IMAPCAUSE" "${1}"; }
debug_log "learn-ham on imap.cause=${IMAPCAUSE}: from=${FROM}, to=${TO}, subject=${SUBJECT}, msgid=${MSGID}, X-Spamd-Result=${XSpamdResult}";

# Ham-learning by storing a copy of the message into spam@example.com
debug_log "learn-ham copy to INBOX/report_ham";
pipe :copy "dovecot-lda" [ "-d", "spam@example.com", "-m", "INBOX/report_ham" ];
```

Prepare Dovecot and compile global Sieve scripts:

```bash
$ ln -s /usr/lib/dovecot/dovecot-lda /usr/local/sbin/dovecot-lda
$ sievec /var/lib/dovecot/sieve/learn-spam.sieve
$ sievec /var/lib/dovecot/sieve/learn-ham.sieve
```

