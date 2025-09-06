#!/usr/bin/env python3
"""Script to remove users from the Zulip organization whose emails are not on the Mailchimp list."""

from configparser import ConfigParser
from zulip import Client as ZulipClient
from mailchimp_marketing import Client as MailchimpClient
from mailchimp_marketing.api_client import ApiClientError

# Read configuration file from config.ini
config = ConfigParser()
config.read("config.ini")

# Load configuration for Zulip and Mailchimp
zulip_client = ZulipClient(**config["zulip"])
mailchimp_client = MailchimpClient()
mailchimp_client.set_config(config["mailchimp"])

# Fetch the list of users from Zulip
zulip_user_list = zulip_client.get_users()

if not zulip_user_list["result"] == "success":
    raise ValueError(f"Failed to fetch users from Zulip: {zulip_user_list}")

for user in zulip_user_list["members"]:
    print(user["full_name"], user["email"])

    # skip bots and anyone with an email on the ftcunion.org domain
    if user["is_bot"]:
        print("Skipping bot", user["full_name"])
        continue
    elif user["delivery_email"].endswith("@ftcunion.org"):
        print("Skipping ftcunion.org user", user["full_name"])
        continue
    elif user["delivery_email"]:
        # Check if the user is in the Mailchimp list
        print(
            f"Checking Mailchimp for user {user['full_name']} <{user['delivery_email']}>"
        )
        try:
            mailchimp_response = mailchimp_client.searchMembers.search(
                query=user["delivery_email"],
                fields=[
                    "exact_matches.members.email_address",
                    "exact_matches.members.full_name",
                    "exact_matches.members.status",
                ],
            )
        except ApiClientError as error:
            print(f"Error searching Mailchimp members: {error.text}")
            continue

        matching_members = mailchimp_response["exact_matches"]["members"]

        if (
            isinstance(matching_members, list)
            and len(matching_members) > 0
            and matching_members[0]["status"] == "subscribed"
        ):
            print("~~> User found in Mailchimp, not removing")
            print("")
            continue
        else:
            print(
                f"~~> Removing user {user['full_name']} <{user['delivery_email']}> from Zulip"
            )
            remove_response = zulip_client.deactivate_user_by_id(user["user_id"])
            if remove_response["result"] == "success":
                print("~~> Successfully removed user")
            else:
                print(f"~~> Failed to remove user: {remove_response}")
            print("")
