#!/bin/sh
"true" '''\'
exec "$(dirname "$(readlink -f "$0")")"/.venv/bin/python "$0" "$@"
'''
"""Script to invite users to the Zulip organization given a list of email addresses in stdin."""

import pathlib
from sys import stdin
from configparser import ConfigParser
from zulip import Client as ZulipClient

# read configuration file from config.ini in the same directory as this script
script_dir = pathlib.Path(__file__).parent.resolve()
config = ConfigParser()
config.read(script_dir / "config.ini")

# load configuration for Zulip and Mailchimp
zulip_client = ZulipClient(**config["zulip"])

for line in stdin:
    email = line.strip()

    # validate email format very basically
    if email and len(email.split("@")) == 2:
        print(f"Inviting {email} to Zulip")
        request = {
            "invitee_emails": email,
            "invite_expires_in_minutes": 60 * 24 * 30,  # 30 days
            "invite_as": 400,  # member
            "stream_ids": [],  # no streams
            "include_realm_default_subscriptions": True,
            "notify_referrer_on_join": True,
            "welcome_message_custom_text": (
                "Hi! Welcome to the FTC Union chat. You can post anything in #**!general** subject"
                " to [the rules](https://chat.ftcunion.org/#narrow/channel/5-announcements/topic/"
                "Official.20chat.20rules/)."
            ),
        }
        print(request)
        response = zulip_client.call_endpoint(
            url="/invites", method="POST", request=request
        )
        if response["result"] == "success":
            print("~~> Success!")
        else:
            print(f"~~> Failure: {response}")
        print("")
    else:
        print(f"Does not seem like an email address: {email}")
        print("")
