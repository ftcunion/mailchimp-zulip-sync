#!/bin/sh
"true" '''\'
exec "$(dirname "$(readlink -f "$0")")"/.venv/bin/python "$0" "$@"
'''
"""Script to remove users from the Zulip organization whose emails are not on the Mailchimp list."""

import pathlib
import time
from configparser import ConfigParser
from zulip import Client as ZulipClient
from mailchimp_marketing import Client as MailchimpClient
from mailchimp_marketing.api_client import ApiClientError

# read configuration file from config.ini in the same directory as this script
script_dir = pathlib.Path(__file__).parent.resolve()
config = ConfigParser()
config.read(script_dir / "config.ini")

# load configuration for Zulip and Mailchimp
zulip_client = ZulipClient(**config["zulip"])
mailchimp_client = MailchimpClient()
mailchimp_client.set_config(config["mailchimp"])

# fetch the list of users from Zulip
zulip_user_list = zulip_client.get_users()

# create last_mailchimp_call variable to rate limit mailchimp api calls
last_mailchimp_call = 0

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
    if user["delivery_email"] and user["delivery_email"].endswith("@ftcunion.org"):
        print(
            f"Skipping ftcunion.org user {user['full_name']} <{user['delivery_email']}>"
        )
        continue
    # if not bypassed, check if the user is in the Mailchimp list
    if user["delivery_email"]:
        # rate limit Mailchimp API calls to 1 per second
        tdiff = time.time() - last_mailchimp_call
        if tdiff < 1:
            time.sleep(1 - tdiff)

        # search for the user in Mailchimp
        print(
            f"Checking Mailchimp for user {user['full_name']} <{user['delivery_email']}>",
            end="",
        )
        try:
            # set last_mailchimp_call to the current unix time
            last_mailchimp_call = time.time()
            # retrieve the email, name, status, and merge fields of the user
            mailchimp_response = mailchimp_client.searchMembers.search(
                query=user["delivery_email"],
                fields=[
                    "exact_matches.members.contact_id",
                    "exact_matches.members.list_id",
                    "exact_matches.members.email_address",
                    "exact_matches.members.full_name",
                    "exact_matches.members.status",
                    "exact_matches.members.merge_fields",
                ],
            )
        except ApiClientError as error:
            print(f"Error searching Mailchimp members: {error.text}")
            continue

        matching_members = mailchimp_response["exact_matches"]["members"]

        # if the user is found in Mailchimp and is subscribed, skip removal and add zulip merge field if not present
        # otherwise, disable the user in Zulip
        if (
            isinstance(matching_members, list)
            and len(matching_members) > 0
            and matching_members[0]["status"] == "subscribed"
        ):
            print(", [FOUND]")
            # add the ZULIP merge field if not present
            if (
                "ZULIP" not in matching_members[0]["merge_fields"].keys()
                or matching_members[0]["merge_fields"]["ZULIP"] != user["user_id"]
            ):
                # create the request body to update the merge field
                update_body = {
                    "merge_fields": matching_members[0]["merge_fields"].copy()
                }
                # set the ZULIP merge field to the user's Zulip user ID
                update_body["merge_fields"]["ZULIP"] = user["user_id"]

                # update the member in Mailchimp
                try:
                    patch_response = mailchimp_client.lists.update_list_member(
                        matching_members[0]["list_id"],
                        matching_members[0]["contact_id"],
                        update_body,
                    )
                except ApiClientError as error:
                    print(f"Error setting ZULIP merge field: {error.text}")
                    continue

                if ("status" not in patch_response.keys()) or (
                    not isinstance(patch_response["status"], int)
                ):
                    print(f"~~> Added ZULIP merge field for user {user['full_name']}")
                else:
                    print(
                        f"~~> Failed to add ZULIP merge field for user {user['full_name']}: {patch_response}"
                    )
            continue

    # remove the user if either they have no delivery email or are not found in Mailchimp
    print(", [NOT FOUND]")
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
    continue
