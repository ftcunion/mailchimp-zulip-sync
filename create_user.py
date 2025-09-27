#!/bin/sh
"true" """\'
exec "$(dirname "$(readlink -f "$0")")"/.venv/bin/python "$0" "$@"
"""
"""Script to forcibly create users in the Zulip organization given a list of email addresses in stdin."""

import secrets
import string
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


# Function to generate a random password
def generate_password(length: int = 12) -> str:
    """Generate a random password."""
    characters = string.digits + string.ascii_letters + string.punctuation
    return "".join(secrets.choice(characters) for i in range(length))


# Function to convert a number to a base62 string
def to_base62(num: int) -> str:
    """Convert a number to a base62 string."""
    if num == 0:
        return "0"
    chars = string.digits + string.ascii_letters
    base62 = ""
    while num > 0:
        num, i = divmod(num, 62)
        base62 = chars[i] + base62
    return base62


for line in stdin:
    email = line.strip()

    # validate email format very basically
    if email and len(email.split("@")) == 2:

        # Generate a random password and user's name
        temporary_password = generate_password(length=12)
        temporary_full_name = f"CHANGEME {to_base62(hash(email) % (62**8))}"

        print(f"Creating {email} in Zulip")
        request = {
            "email": email,
            "password": temporary_password,
            "full_name": temporary_full_name,
        }
        print(request)
        response = zulip_client.create_user(request)
        if response["result"] == "success":
            print("~~> Success!")
        else:
            print(f"~~> Failure: {response}")
        print("")
    else:
        print(f"Does not seem like an email address: {email}")
        print("")
