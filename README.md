# Mailchimp Zulip sync

These are python scripts to keep members in Zulip consistent with the master list in Mailchimp.

The scripts require a config.ini file with the following structure:

```ini
[mailchimp]
api_key = 00000000000000000000000000000000-aa00
server_prefix = aa00

[zulip]
email = aaaa-bot@xxxx.zulipchat.com
api_key = 00000000000000000000000000000000
site=https://xxxx.zulipchat.com
```
