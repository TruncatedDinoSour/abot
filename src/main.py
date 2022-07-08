#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abot for ari-web"""

import asyncio
import json
import os
import sys
from secrets import SystemRandom
from typing import Any, Callable, Optional
from uuid import uuid4
from warnings import filterwarnings as filter_warnings

import aiohttp  # type: ignore

CONFIG_FILE: str = "config.json"
CONFIG: dict[str, Any] = {
    "max-cache": 10000,
    "bot-name": "example-abot",
    "vm": "vm0",
    "init-message": "Hello, world!",
    "bye-message": "Goodbye, world!",
    "notes": {},
}
GUAC_CACHE: dict[str, dict[Any, Any]] = {"guac": {}, "unguac": {}}
RANDOM: SystemRandom = SystemRandom()
AUTH: dict[str, Any] = {"users": set(), "key": uuid4().hex}
STATE: dict[str, bool] = {"run": True}


def reset_authkey() -> None:
    AUTH["key"] = uuid4().hex
    log(f"New auth key: {AUTH['key']}")


def save_config() -> None:
    log("Saving config")

    with open(CONFIG_FILE, "w") as cfg:
        json.dump(CONFIG, cfg, indent=4)

    with open(CONFIG_FILE, "r") as cfg:
        CONFIG.update(json.load(cfg))


def guac_msg(*args: str) -> str:
    _cache = GUAC_CACHE["guac"]

    if len(_cache) > CONFIG["max-cache"]:
        _cache.clear()
    elif args in GUAC_CACHE:
        return _cache[args]

    msg: str = f"{','.join(f'{len(arg)}.{arg}' for arg in args)};"
    _cache[args] = msg

    return msg


def log(msg: str) -> None:
    print(f" :: {msg}")


def unguac_msg(msg: str) -> Optional[list[str]]:
    if not msg:
        return []

    _cache = GUAC_CACHE["unguac"]

    if len(_cache) > CONFIG["max-cache"]:
        _cache.clear()
    elif msg in _cache:
        return _cache[msg]

    idx: int = 0
    result: list[str] = []
    chars: list[str] = list(msg)

    while True:
        dist_str: str = ""

        while chars[idx].isdecimal():
            dist_str += chars[idx]
            idx = idx + 1

        if idx >= 1:
            idx -= 1

        distance: int = 0

        if dist_str.isdigit():
            distance = int(dist_str)
        else:
            return None

        idx += 1

        if chars[idx] != ".":
            return None

        idx += 1

        addition: str = ""
        for num in range(idx, idx + distance):
            addition += chars[num]

        result.append(addition)

        idx += distance

        if idx >= len(chars):
            return None

        if chars[idx] == ",":
            pass
        elif chars[idx] == ";":
            break
        else:
            return None

        idx += 1

    _cache[msg] = result

    return result


class CommandParser:
    @staticmethod
    def cmd_hi(user: str, args: list[str]) -> tuple[str]:
        """Noauth command, says hello to the user
        Syntax: hi"""

        return (guac_msg("chat", f"Hello, @{user}"),)

    @staticmethod
    def cmd_log(user: str, args: list[str]) -> tuple[str]:
        """Noauth command, authenticates the user
        Syntax: log <me|user> <in|out> <auth key>"""

        if len(args) < 3:
            return (guac_msg("chat", "Uhh, I need <me|user> <in|out> <auth key>"),)

        if args[-1] != AUTH["key"]:
            return (guac_msg("chat", f"@{user} your auth key is invalid lmao"),)

        auth_user: str = args[0]
        if args[0] == "me":
            auth_user = user

        reset_authkey()

        if args[1] == "in":
            if auth_user in AUTH["users"]:
                return (guac_msg("chat", f"{auth_user} is already authenticated"),)

            AUTH["users"].add(auth_user)
        elif args[1] == "out":
            if auth_user not in AUTH["users"]:
                return (guac_msg("chat", f"{auth_user} is not authenticated"),)

            AUTH["users"].add(auth_user)
        else:
            return (guac_msg("chat", f"How do I log {args[1]!r} a person out???"),)

        return (guac_msg("chat", f"@{auth_user} you have been logged {args[1]}"),)

    @staticmethod
    def cmd_getkey(user: str, args: list[str]) -> tuple[str]:
        """Noauth command, authenticates the user
        Syntax: getkey"""

        log(f"{user!r} requested auth key: {AUTH['key']}")
        return (guac_msg("chat", f"@{user} check the console for the key"),)

    @staticmethod
    def cmd_whoami(user: str, args: list[str]) -> tuple[str]:
        """Auth command, authenticates the user
        Syntax: getkey"""

        return (guac_msg("chat", f"{user}"),)

    @staticmethod
    def cmd_die(user: str, args: list[str]) -> tuple[str]:
        """Auth command, exists the server
        Syntax: die"""

        STATE["run"] = False

        if CONFIG["bye-message"]:
            return (guac_msg("chat", CONFIG["bye-message"]),)

        return (guac_msg("nop"),)

    @staticmethod
    def cmd_savecfg(user: str, args: list[str]) -> tuple[str]:
        """Auth command, saves the config
        Syntax: savecfg"""

        save_config()
        return (guac_msg("chat", f"{CONFIG_FILE!r} saved"),)

    @staticmethod
    def cmd_note(user: str, args: list[str]) -> tuple[str]:
        """Auth command, makes a note and then saves the config
        Syntax: note <name> <content...>"""

        if len(args) < 2:
            return (
                guac_msg(
                    "chat", "Huh? I kinda need the <name> and the <conrent> of the note"
                ),
            )

        CONFIG["notes"][args[0]] = " ".join(args[1:])

        save_config()
        return (guac_msg("chat", f"Note {args[0]!r} saved <3"),)

    @staticmethod
    def cmd_get(user: str, args: list[str]) -> tuple[str]:
        """Auth command, gets a note
        Syntax: get <name>"""

        if not len(args):
            return (guac_msg("chat", "What note do you need lol"),)

        if args[0] not in CONFIG["notes"]:
            return (guac_msg("chat", "That's not a note... zamn"),)

        return (guac_msg("chat", f">{CONFIG['notes'][args[0]]}"),)

    @staticmethod
    def cmd_del(user: str, args: list[str]) -> tuple[str]:
        """Auth command, deletes a note
        Syntax: del <name>"""

        if not len(args):
            return (guac_msg("chat", "What note do you want me to rm -rf?"),)

        if args[0] not in CONFIG["notes"]:
            return (guac_msg("chat", "That's not note, such shame"),)

        del CONFIG["notes"][args[0]]

        save_config()
        return (guac_msg("chat", f"Note {args[0]!r} deleted, sad to see it go kinda"),)


class ChatParser:
    @staticmethod
    def type_nop(content: list[str]) -> tuple[str]:
        return (guac_msg("nop"),)

    @classmethod
    def type_chat(cls, content: list[str]) -> tuple[str]:
        if len(content) > 3:
            return cls.type_nop(content)

        if content[1].startswith(f"@{CONFIG['bot-name']}"):
            user: str = content[0]
            command: list[str] = " ".join(content[1:]).split()[1:]

            log(f"User {user!r} invoked {command!r}")

            if not command:
                return (guac_msg("chat", "Huh? What do you want lol"),)

            cmd_handler: Optional[Callable] = getattr(
                CommandParser, f"cmd_{command[0]}", None
            )

            if cmd_handler is None:
                return (guac_msg("chat", f"Lmao what even is {command[0]!r}?"),)

            if (cmd_handler.__doc__ or "").strip().startswith("Noauth"):
                return cmd_handler(user, command[1:])

            if user not in AUTH["users"]:
                return (
                    guac_msg("chat", f"Hey {user!r}, you are not authenticated :("),
                )

            return cmd_handler(user, command[1:])

        return cls.type_nop(content)

    @classmethod
    def type_adduser(cls, content: list[str]) -> tuple[str]:
        if RANDOM.randint(0, 100) == 96:
            log(f"Welcoming {content[1]!r}")
            return (guac_msg("chat", f"Welcome, {content[1]!r}. How are you?"),)

        return cls.type_nop(content)

    @classmethod
    def type_remuser(cls, content: list[str]) -> tuple[str]:
        if RANDOM.randint(0, 100) == 69:
            log(f"Saying goobye to {content[1]!r}")
            return (guac_msg("chat", f"Goodbye, {content[1]!r}. Have a nice day"),)

        return cls.type_nop(content)


async def main() -> int:
    """Entry/main function"""

    if not os.path.isfile(CONFIG_FILE):
        log(f"Making default config in {CONFIG_FILE!r}")

        with open(CONFIG_FILE, "w") as cfg:
            json.dump(CONFIG, cfg, indent=4)
    else:
        with open(CONFIG_FILE, "r") as cfg:
            CONFIG.update(json.load(cfg))

    s: aiohttp.ClientSession = aiohttp.ClientSession()
    url: str = f"wss://computernewb.com/collab-vm/{CONFIG['vm']}/"

    log(f"Connecting to {url}")

    async with s.ws_connect(
        url,
        protocols=["guacamole"],
        origin="https://computernewb.com",
        autoclose=False,
        autoping=False,
    ) as ws:
        await ws.send_str(guac_msg("rename", CONFIG["bot-name"]))
        await ws.send_str(guac_msg("connect", CONFIG["vm"]))

        log("Connected")

        if CONFIG["init-message"].strip():
            await ws.send_str(guac_msg("chat", CONFIG["init-message"]))

        log(f"Auth key: {AUTH['key']}")

        async for msg in ws:
            parsed_msg: Optional[list[str]] = unguac_msg(msg.data)

            if parsed_msg is None:
                ws.send_str(
                    guac_msg("chat", f"The guac parser failed on message: {msg!r}")
                )
                continue

            for cmsg in (
                getattr(ChatParser, f"type_{parsed_msg[0]}", None)
                or ChatParser.type_nop
            )(parsed_msg[1:]):
                await ws.send_str(cmsg)

            if not STATE["run"]:
                log("Run state was set to false")
                await ws.close()
                break

    save_config()

    await s.close()

    return 0


if __name__ == "__main__":
    assert main.__annotations__.get("return") is int, "main() should return an integer"

    filter_warnings("error", category=Warning)
    sys.exit(asyncio.run(main()))
