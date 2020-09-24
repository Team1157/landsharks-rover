"""
Command-line utility for managing rover users
"""

import click
import os
import json
from getpass import getpass
import bcrypt


@click.group()
@click.option("-f", "--file", "filename", default=os.path.join("base_station", "rover_users.json"), show_default=True)
@click.pass_context
def rover_user(ctx, filename):
    """
    Command-line utility for managing rover users and permissions
    """
    # Make sure context is a dict
    ctx.ensure_object(dict)
    # Hold onto filename for write later
    ctx.obj["file"] = filename
    # Read file
    try:
        with open(filename, "r") as f:
            ctx.obj["users"] = json.load(f)
    # Warning and continue if userbase file does not exist
    except FileNotFoundError:
        click.echo(f"Initialized new userbase file in {filename}")
        ctx.obj["users"] = {}
    # Exit if malformed JSON
    except json.JSONDecodeError:
        click.echo("Unable to open userbase file: file contains malformed JSON", err=True)
        raise SystemExit(1)


def store_userbase(ctx):
    # Write userbase
    try:
        with open(ctx.obj["file"], "w") as f:
            json.dump(ctx.obj["users"], f)
    # Exit if can't open file
    except PermissionError:
        click.echo(f"Unable to write userbase file: permission error", err=True)
        raise SystemExit(1)


@rover_user.command()
@click.argument("username")
@click.pass_context
def add(ctx, username):
    """
    Adds a new user to the userbase
    """
    # Exit if user exists
    if username in ctx.obj["users"]:
        click.echo(f"Unable to add user: user {username} exists", err=True)
        raise SystemExit(1)
    # Create user stub
    ctx.obj["users"][username] = {
        "pw_hash": "",
        "groups": []
    }
    # Pass on to set password
    ctx.invoke(change_password, username=username)


@rover_user.command()
@click.argument("username")
@click.pass_context
def remove(ctx, username):
    """
    Removes a user from the userbase
    """
    # Exit if user does not exist
    if username not in ctx.obj["users"]:
        click.echo(f"Unable to remove user: user {username} does not exist", err=True)
        raise SystemExit(1)
    # Delete user
    del ctx.obj["users"][username]
    # Store modified userbase
    store_userbase(ctx)


@rover_user.command()
@click.pass_context
def list_users(ctx):
    """
    Lists all registered users
    """
    # List users
    click.echo(", ".join(ctx.obj["users"].keys()))


@rover_user.command()
@click.argument("username")
@click.pass_context
def change_password(ctx, username):
    """
    Changes the password of a user
    """
    # Exit if user does not exist
    if username not in ctx.obj["users"]:
        click.echo(f"Unable to change user password: user {username} does not exist", err=True)
        raise SystemExit(1)
    # Get new password, encode into bytes as utf-8
    pw = getpass(f"New password for user {username}: ").encode("utf-8")
    # Hash password, reencode to ASCII so json doesn't complain (bcrypt shouldn't output any non-ASCII data)
    ctx.obj["users"][username]["pw_hash"] = bcrypt.hashpw(pw, bcrypt.gensalt()).decode("ascii")
    # Store modified userbase
    store_userbase(ctx)


@rover_user.command()
@click.argument("username")
@click.argument("groups", nargs=-1)
@click.pass_context
def add_groups(ctx, username, groups):
    """
    Adds the user to one or more groups
    """
    # Exit if user does not exist
    if username not in ctx.obj["users"]:
        click.echo(f"Unable to add user groups: user {username} does not exist", err=True)
        raise SystemExit(1)
    # Add groups
    ctx.obj["users"][username]["groups"] = list(set(ctx.obj["users"][username]["groups"]).union(set(groups)))
    # Store modified userbase
    store_userbase(ctx)


@rover_user.command()
@click.argument("username")
@click.argument("groups", nargs=-1)
@click.pass_context
def remove_groups(ctx, username, groups):
    """
    Removes the user from one or more groups
    """
    if username not in ctx.obj["users"]:
        click.echo(f"Unable to remove user groups: user {username} does not exist", err=True)
        raise SystemExit(1)
    # Remove groups
    for group in groups:
        ctx.obj["users"][username]["groups"].pop(group)
    # Store modified userbase
    store_userbase(ctx)


@rover_user.command()
@click.argument("username")
@click.pass_context
def list_groups(ctx, username):
    """
    Lists the groups a user belongs to
    """
    # Exit if user does not exist
    if username not in ctx.obj["users"]:
        click.echo(f"Unable to list user groups: user {username} does not exist", err=True)
        raise SystemExit(1)
    # List groups
    click.echo(", ".join(ctx.obj["users"][username]["groups"]))


if __name__ == '__main__':
    rover_user(obj={})
