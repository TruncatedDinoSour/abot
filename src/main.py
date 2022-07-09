#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abot for collabvm"""

import asyncio
import json
import os
import sys
from html import unescape as html_unescape
from secrets import SystemRandom
from time import sleep
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from uuid import uuid4
from warnings import filterwarnings as filter_warnings

import aiohttp  # type: ignore
import requests  # type: ignore

CONFIG_FILE: str = "config.json"
CONFIG: Dict[str, Any] = {
    "max-cache": 10000,
    "bot-name": "example-abot",
    "vm": "vm0",
    "init-message": "Hello, world!",
    "bye-message": "Goodbye, world!",
    "notes": {},
    "ignored": [],
    "insults": {
        "adjectives": [
            "huge",
            "shitty",
            "idiotic",
            "stupid",
            "deformed",
            "cranky",
            "weird",
            "trashy",
            "unskilled",
            "",
        ],
        "nouns": [
            "turnip",
            "punchbag",
            "kid",
            "dog",
            "asshole",
            "hairball",
            "dumpster rat",
            "dumpsterfire",
            "wet-wipe",
            "hag",
            "shit",
            "skid",
        ],
        "descriptors": ["piece of", "chunk of", "son of a", ""],
    },
    "user-name": "guest12345",
    "aliases": {},
}
RANDOM: SystemRandom = SystemRandom()


def gen_key() -> str:
    _key: list[str] = list(
        f"{hex(RANDOM.randint(0, 123456789))}{uuid4().hex}{RANDOM.randint(0, 123456789101112)}"
    )
    RANDOM.shuffle(_key)
    return "".join(_key)


GUAC_CACHE: Dict[str, Dict[Any, Any]] = {"guac": {}, "unguac": {}}
AUTH: Dict[str, Any] = {"users": set(), "key": gen_key()}
STATE: Dict[str, bool] = {"run": True}


def paste(content: str, no_content_msg: str) -> Union[str, Tuple[None, str]]:
    if not content:
        return None, guac_msg("chat", no_content_msg)

    burl: str = "https://www.toptal.com/developers/hastebin"

    pid = requests.post(
        f"{burl}/documents",
        data=content,
    )

    if pid.status_code != 200:
        log(f"Failed to POST to {burl!r}")
        return None, f"Failed to POST to pastebin (code {pid.status_code})"

    return f"{burl}/{pid.json()['key']}.md"


def reset_authkey() -> None:
    AUTH["key"] = gen_key()
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


def unguac_msg(msg: str) -> Optional[List[str]]:
    if not msg:
        return []

    _cache = GUAC_CACHE["unguac"]

    if len(_cache) > CONFIG["max-cache"]:
        _cache.clear()
    elif msg in _cache:
        return _cache[msg]

    idx: int = 0
    result: List[str] = []
    chars: List[str] = list(msg)

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
    def cmd_hi(user: str, args: List[str]) -> Tuple[str]:
        """Noauth command, says hello to the user
        Syntax: hi"""

        return (guac_msg("chat", f"Hello, @{user} :}}"),)

    @staticmethod
    def cmd_log(user: str, args: List[str]) -> Tuple[str]:
        """Noauth command, authenticates the user
        Syntax: log <me|user> <in|out> <auth key>"""

        if len(args) < 3:
            return (guac_msg("chat", "Uhh, I need <me|user> <in|out> <auth key>"),)

        if args[-1] != AUTH["key"]:
            return (guac_msg("chat", f"@{user} your auth key is invalid lmao"),)

        reset_authkey()

        auth_user: str = args[0]
        if args[0] == "me":
            auth_user = user

        if auth_user in CONFIG["ignored"]:
            return (guac_msg("chat", f"{auth_user!r} is ignored for a reason :|"),)

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
    def cmd_getkey(user: str, args: List[str]) -> Tuple[str]:
        """Noauth command, authenticates the user
        Syntax: getkey"""

        log(f"{user!r} requested auth key: {AUTH['key']}")
        return (guac_msg("chat", f"@{user} check the console for the key"),)

    @staticmethod
    def cmd_whoami(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, authenticates the user
        Syntax: getkey"""

        return (guac_msg("chat", f"You are {user} :D"),)

    @staticmethod
    def cmd_die(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, exists the server
        Syntax: die"""

        STATE["run"] = False

        if CONFIG["bye-message"]:
            return (guac_msg("chat", CONFIG["bye-message"]),)

        return (guac_msg("nop"),)

    @staticmethod
    def cmd_savecfg(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, saves the config
        Syntax: savecfg"""

        save_config()
        return (guac_msg("chat", f"{CONFIG_FILE!r} saved"),)

    @staticmethod
    def cmd_note(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, makes a note and then saves the config
        Syntax: note <name> <content...>"""

        if len(args) < 2:
            return (
                guac_msg(
                    "chat", "Huh? I kinda need the <name> and the <conrent> of the note"
                ),
            )

        if args[0] in CONFIG["notes"]:
            return (guac_msg("chat", "Lol, nah, note {args[0]!r} already exists ;)"),)

        CONFIG["notes"][args[0]] = " ".join(args[1:])

        save_config()
        return (guac_msg("chat", f"Note {args[0]!r} saved <3"),)

    @staticmethod
    def cmd_get(user: str, args: List[str]) -> Tuple[str]:
        """Noauth command, gets a note
        Syntax: get <name>"""

        if not args:
            return (guac_msg("chat", "What note do you need lol"),)

        if args[0] not in CONFIG["notes"]:
            return (guac_msg("chat", "That's not a note... zamn"),)

        return (guac_msg("chat", f"> {CONFIG['notes'][args[0]]}"),)

    @staticmethod
    def cmd_del(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, deletes a note
        Syntax: del <name>"""

        if not args:
            return (guac_msg("chat", "What note do you want me to rm -rf?"),)

        if args[0] not in CONFIG["notes"]:
            return (guac_msg("chat", "That's not note, such shame"),)

        del CONFIG["notes"][args[0]]

        save_config()
        return (guac_msg("chat", f"Note {args[0]!r} deleted, sad to see it go kinda"),)

    @staticmethod
    def cmd_notes(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, lists the notes
        Syntax: notes"""

        pid = paste(
            "\n".join(f"* {note}" for note in CONFIG["notes"]),
            f"@{user} No notes to show you, want some tea though?",
        )

        if pid[0] is None:
            return (pid[1],)

        return (guac_msg("chat", f"@{user} Here's a list of notes: {pid}"),)

    @staticmethod
    def cmd_ignore(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, ignores a user
        Syntax: ignore <user>"""

        if not args:
            return (guac_msg("chat", "Who do I even ignore lmao???????"),)

        if args[0] in AUTH["users"]:
            return (
                guac_msg(
                    "chat",
                    "Yeah... no, I don't think ignoring authenticated users is a good idea",
                ),
            )

        if args[0] in CONFIG["ignored"]:
            return (guac_msg("chat", "You want me to ignore an already ignored user?"),)

        CONFIG["ignored"].append(args[0])
        save_config()

        return (
            guac_msg(
                "chat",
                f"@{args[0]}'s commands will be ignored from now on lmao, imagine",
            ),
        )

    @staticmethod
    def cmd_acknowledge(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, acknowledges a user
        Syntax: acknowledge <user>"""

        if not args:
            return (guac_msg("chat", "Hm? Who do you want me to acknowledge?"),)

        if args[0] not in CONFIG["ignored"]:
            return (
                guac_msg(
                    "chat",
                    "They're not ignored lol, you trying to say something? :eyes:",
                ),
            )

        CONFIG["ignored"].remove(args[0])
        save_config()

        return (
            guac_msg(
                "chat",
                f"@{args[0]}'s commands will be not ignored from now on :)",
            ),
        )

    @staticmethod
    def cmd_ignored(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, lists the ignored users
        Syntax: ignored"""

        pid = paste(
            "\n".join(f"* {ignored}" for ignored in CONFIG["ignored"]),
            f"@{user} No users being ignored, which is a good thing I presume?",
        )

        if pid[0] is None:
            return (pid[1],)

        return (
            guac_msg("chat", f"@{user} Here's ur a list of ignored ppl heh: {pid}"),
        )

    @staticmethod
    def cmd_insult(user: str, args: List[str]) -> Tuple[str]:
        """Noauth command, insults a specified user
        Syntax: insult <user>"""

        if not args:
            return (guac_msg("chat", "I like.. need the <user> to insult them lmao"),)

        if args[0] == "me":
            args[0] = user

        return (
            guac_msg(
                "chat",
                " ".join(
                    f"@{args[0]} you are a {' '.join(RANDOM.choice(CONFIG['insults'][_from]) for _from in ('descriptors', 'adjectives', 'nouns'))}".split()
                ),
            ),
        )

    @staticmethod
    def cmd_revokey(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, revoke current auth key
        Syntax: revokey"""

        reset_authkey()
        return (guac_msg("chat", f"@{user} the current auth key has been revoked"),)

    @staticmethod
    def cmd_alias(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, aliases a command to a command
        Syntax: alias <name> <content...>"""

        if len(args) < 2:
            return (
                guac_msg(
                    "chat",
                    f"@{user} O, You made a mistake lmao, gimme the <name> AND the <content...>",
                ),
            )

        if args[0] in CONFIG["aliases"]:
            return (
                guac_msg(
                    "chat",
                    f"@{user} alias {args[0]!r} already exists :(",
                ),
            )

        CONFIG["aliases"][args[0]] = " ".join(args[1:])
        save_config()

        return (guac_msg("chat", f"Alias {args[0]!r} saved"),)

    @staticmethod
    def cmd_unalias(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, unaliases an alias
        Syntax: unalias <name>"""

        if not args:
            return (
                guac_msg(
                    "chat",
                    f"@{user} Hm? What do I need to unalias?",
                ),
            )

        if args[0] not in CONFIG["aliases"]:
            return (
                guac_msg(
                    "chat",
                    f"@{user} I'm like... 101% sure alias {args[0]!r} doesn't exist",
                ),
            )

        del CONFIG["aliases"][args[0]]
        save_config()

        return (guac_msg("chat", f"Unaliased {args[0]!r}"),)

    @staticmethod
    def cmd_aliases(user: str, args: List[str]) -> Tuple[str]:
        """Auth command, lists the aliases
        Syntax: aliases"""

        pid = paste(
            "\n".join(
                f"* {name} (@{CONFIG['bot-name']} {value})"
                for name, value in CONFIG["aliases"].items()
            ),
            f"@{user} ...what do I even show you lol, there's no aliases",
        )

        if pid[0] is None:
            return (pid[1],)

        return (guac_msg("chat", f"@{user} Here's a list of your aliases: {pid}"),)


class ChatParser:
    @staticmethod
    def type_nop(content: List[str]) -> Tuple[str]:
        return (guac_msg("nop"),)

    @classmethod
    def type_chat(cls, content: List[str]) -> Tuple[str]:
        if len(content) > 3:
            return cls.type_nop(content)

        user: str = content[0]

        if user in CONFIG["ignored"] or user == CONFIG["bot-name"]:
            return cls.type_nop(content)

        if content[1].lower().strip() == CONFIG["user-name"]:
            if user == CONFIG["user-name"]:
                return cls.type_nop(content)

            return (guac_msg("chat", f"@{user} smh whattttttttttttt"),)

        command: List[str] = list(map(html_unescape, " ".join(content[1:]).split()[1:]))  # type: ignore
        _dad_joke_im: str = content[1].lower().split(" ", 1)[0]

        if (
            _dad_joke_im in ("i&#x27;m", "im")
            or _dad_joke_im == "i"
            and command[0].lower() == "am"
        ):
            if command[0].lower() == "am":
                command = command[1:]

            if len(command) < 1:
                return cls.type_nop(content)

            return (
                guac_msg(
                    "chat", f"Hi {' '.join(command)}, I'm {CONFIG['bot-name']} :)"
                ),
            )

        _bot_mention: str = f"@{CONFIG['bot-name']}"

        if content[1].startswith(_bot_mention) and not len(command):
            log(f"{user!r} mentioned the bot without a command")
            return (guac_msg("chat", f"@{user} Huh? What do you want lol"),)

        if content[1].startswith(f"{_bot_mention} "):
            log(f"User {user!r} invoked {command!r}")

            cmd_handler: Optional[Callable] = getattr(
                CommandParser, f"cmd_{command[0]}", None
            )

            if cmd_handler is None:
                if command[0] in CONFIG["aliases"]:
                    log(f"Found alias: {command[0]!r}")

                    try:
                        return cls.type_chat(
                            [
                                user,
                                f"@{CONFIG['bot-name']} {CONFIG['aliases'][command[0]]}",
                            ]
                        )
                    except RecursionError:
                        log(f"Recursive alias detected: {command[0]!r}")

                        return (
                            guac_msg(
                                "chat", "ZAMN! Your alias is *extremely* recursive"
                            ),
                        )

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
    def type_adduser(cls, content: List[str]) -> Tuple[str]:
        if RANDOM.randint(0, 200) == 96:
            log(f"Welcoming {content[1]!r}")
            return (guac_msg("chat", f"Welcome, {content[1]!r}. How are you?"),)

        return cls.type_nop(content)

    @classmethod
    def type_remuser(cls, content: List[str]) -> Tuple[str]:
        if content[1] in AUTH["users"]:
            log(f"Logging {content[1]!r} out")
            AUTH["users"].remove(content[1])

        if RANDOM.randint(0, 200) == 69:
            log(f"Saying goodbye to {content[1]!r}")
            return (guac_msg("chat", f"Goodbye, {content[1]!r}. Have a nice day"),)

        return cls.type_nop(content)

    @classmethod
    def type_rename(cls, content: List[str]) -> Tuple[str]:
        if content[2] in AUTH["users"]:
            log(f"User has renamed themselves so logging {content[2]!r} out")
            AUTH["users"].remove(content[2])

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

    log(f"Connecting to {url!r}")

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
            parsed_msg: Optional[List[str]] = unguac_msg(msg.data)

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

    while STATE["run"]:
        log("Running the bot")
        ret: int = asyncio.run(main())

        if STATE["run"]:
            log("Reconnecting after 30s")
            sleep(30)

    sys.exit(ret)
