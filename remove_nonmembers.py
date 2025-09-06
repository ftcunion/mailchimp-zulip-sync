#!/usr/bin/env python3
"""Script to remove users from the Zulip organization whose emails are not on the Mailchimp list."""

from configparser import ConfigParser
from zulip import Client as ZulipClient
from mailchimp_marketing import Client as MailchimpClient
from mailchimp_marketing.api_client import ApiClientError

# read configuration file from config.ini
config = ConfigParser()
config.read("config.ini")

# load configuration for Zulip and Mailchimp
zulip_client = ZulipClient(**config["zulip"])
mailchimp_client = MailchimpClient()
mailchimp_client.set_config(config["mailchimp"])

# fetch the list of users from Zulip
zulip_user_list = zulip_client.get_users()

if zulip_user_list["result"] != "success":
    raise ValueError(f"Failed to fetch users from Zulip: {zulip_user_list}")

for user in zulip_user_list["members"]:
    # skip users who are already deactivated
    if not user["is_active"]:
        print(f"Skipping already deactivated user {user['full_name']}")
        continue
    # skip bots
    if user["is_bot"]:
        print("Skipping bot", user["full_name"])
        continue
    # skip anyone with an email on the ftcunion.org domain
    if user["delivery_email"].endswith("@ftcunion.org"):
        print(
            f"Skipping ftcunion.org user {user['full_name']} <{user['delivery_email']}>"
        )
        continue
    # if not bypassed, check if the user is in the Mailchimp list
    if user["delivery_email"]:
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

        # if the user is found in Mailchimp and is subscribed, skip removal
        # otherwise, disable the user in Zulip
        if (
            isinstance(matching_members, list)
            and len(matching_members) > 0
            and matching_members[0]["status"] == "subscribed"
        ):
            print("~~> User found in Mailchimp, not removing")
            print("")
            continue

        print(
            f"~~> Removing user {user['full_name']} <{user['delivery_email']}> from Zulip"
        )

        # attempt to remove the user from Zulip
        remove_response = zulip_client.deactivate_user_by_id(user["user_id"])

        # check if removal was successful and log/notify accordingly
        if remove_response["result"] == "success":
            print("~~> Successfully removed user")
            # try to tell the #member_bot_log channel about the removal
            zulip_client.send_message(
                {
                    "type": "channel",
                    "to": "member_bot_log",
                    "topic": "deactivations",
                    "content": "Deactivated user "
                    + user["full_name"]
                    + f" <{user['delivery_email']}>",
                }
            )
        else:
            print(f"~~> Failed to remove user: {remove_response}")
            # try to tell the #member_bot_log channel about the removal failure
            zulip_client.send_message(
                {
                    "type": "channel",
                    "to": "member_bot_log",
                    "topic": "errors",
                    "content": "Failed to deactivate user "
                    + user["full_name"]
                    + f" <{user['delivery_email']}>: {remove_response}",
                }
            )
            print("")
        continue

    print(f"Skipping user {user['full_name']} with no delivery email")
    print("")
