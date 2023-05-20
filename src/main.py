#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abot for collabvm"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from html import unescape as html_unescape
from secrets import SystemRandom
from string import punctuation as special_characters
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from uuid import uuid4
from warnings import filterwarnings as filter_warnings

import aiohttp  # type: ignore
import discord_webhook as dw  # type: ignore
import requests  # type: ignore
from guacamole_keysyms import KeyIdentifiers, UnshiftedKeyCodes  # type: ignore

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
    "report-webhook-url": "",
    "authkey-webhook-url": "",
    "chatlog-limit": 500,
    "logs-dir": "logs",
    "autodump-chatlogs": True,
    "impersonators": [],
    "not-impersonators": [
        "general darian",
        "specialized egg",
        "emperor palpatine",
        "mr. ware",
    ],
    "keys": {},
}
RANDOM: SystemRandom = SystemRandom()


def gen_key() -> str:
    _key: list[str] = list(
        f"{hex(RANDOM.randint(0, 123456789))}:{uuid4().hex}:{RANDOM.randint(0, 123456789101112)}"
    )
    RANDOM.shuffle(_key)
    return "".join(_key)


GUAC_CACHE: Dict[str, Dict[Any, Any]] = {
    "guac": {},
    "unguac": {},
    "guac-keys": {},
}
AUTH: Dict[str, Any] = {
    "users": set(),
    "key": "",
}
STATE: Dict[str, Any] = {
    "run": True,
    "vm": "",
    "chatlog": [],
    "sleep": 0,
}
VOTE_STATES: Dict[int, str] = {
    0: "Vote started",
    1: "Someone voted/removed their vote",
    2: "Reset vote ended",
    3: "Timeout for reset",
}
GUAC_KEYS_SPECIAL_MAPPING: Dict[str, Dict[str, UnshiftedKeyCodes]] = {
    "escape": {
        "n": KeyIdentifiers.ENTER,
        "e": KeyIdentifiers.ESCAPE,
        "c": UnshiftedKeyCodes.CTRL,
        "a": KeyIdentifiers.ALT,
        "b": KeyIdentifiers.BACKSPACE,
        "w": KeyIdentifiers.WIN,
        ")": ord(")"),
        "s": KeyIdentifiers.SHIFT,
        "t": KeyIdentifiers.TAB,
        "l": KeyIdentifiers.NUM_LOCK,
    },
    "arrow": {
        "l": KeyIdentifiers.ARROW_LEFT,
        "u": KeyIdentifiers.ARROW_UP,
        "r": KeyIdentifiers.ARROW_RIGHT,
        "d": KeyIdentifiers.ARROW_DOWN,
    },
}


def parse_guac_keys(keys: str) -> Union[List[Tuple[int, int]], str]:
    _cache_name: str = "guac-keys"

    if len(GUAC_CACHE[_cache_name]) > CONFIG["max-cache"]:
        GUAC_CACHE[_cache_name].clear()
    elif keys in GUAC_CACHE[_cache_name]:
        return GUAC_CACHE[_cache_name][keys]

    results: List[Tuple[int, int]] = []
    max_ip: int = len(keys)
    ip: int = 0

    special_chars: Tuple[str, ...] = (
        "@",
        "^",
        "\\",
        "~",
        "[",
        "(",
        "!",
        "{",
        "|",
        "<",
    )

    while ip < max_ip:
        char: str = keys[ip]

        def check_inc_ip(msg: str, /, ip: int = ip) -> Optional[str]:
            ip += 1

            if ip > max_ip:
                print(f"IP overflow: {msg}", file=sys.stderr)
                return msg

            return None

        if char in special_chars:
            match char:
                case "@":
                    _combo_name: str = ""

                    while char != ";":
                        _combo_name += char

                        ip += 1
                        if (ret := check_inc_ip("No combo end")) is not None:
                            return ret
                        char = keys[ip]

                    _combo_name = _combo_name[1:]

                    if _combo_name not in CONFIG["keys"]:
                        return f"No combo {_combo_name!r} found"

                    combo = parse_guac_keys(CONFIG["keys"][_combo_name])

                    if type(combo) == str:
                        return f"{_combo_name}: combo"

                    results.extend(combo)  # type: ignore

                case "^":
                    ip += 1
                    if (
                        ret := check_inc_ip("^ is missing a control character")
                    ) is not None:
                        return ret
                    char = keys[ip]

                    results.extend(
                        (
                            (UnshiftedKeyCodes.CTRL, 1),
                            (ord(char), 1),
                            (ord(char), 0),
                            (UnshiftedKeyCodes.CTRL, 0),
                        )
                    )

                case "\\":
                    ip += 1
                    if (
                        ret := check_inc_ip("\\ is missing a special key character")
                    ) is not None:
                        return ret
                    char = keys[ip]

                    if char not in GUAC_KEYS_SPECIAL_MAPPING["escape"]:
                        return f"Invalid special key char: {char!r}"

                    results.append((GUAC_KEYS_SPECIAL_MAPPING["escape"][char], 1))

                case "~":
                    ip += 1
                    if (
                        ret := check_inc_ip("^ is missing a special key character")
                    ) is not None:
                        return ret
                    char = keys[ip]

                    if char not in GUAC_KEYS_SPECIAL_MAPPING["arrow"]:
                        return f"Invalid arrow key char: {char!r}"

                    results.extend(
                        (
                            (GUAC_KEYS_SPECIAL_MAPPING["arrow"][char], 1),
                            (GUAC_KEYS_SPECIAL_MAPPING["arrow"][char], 0),
                        )
                    )

                case "[":
                    _f_key: str = ""

                    while char != "]":
                        _f_key += char

                        ip += 1
                        if (ret := check_inc_ip("No F escape end")) is not None:
                            return ret
                        char = keys[ip]

                    _f_key = _f_key[1:]

                    if (f_key := getattr(KeyIdentifiers, f"F{_f_key}", None)) is None:
                        return f"Invalid F key: {_f_key!r}"

                    results.extend(((f_key, 1), (f_key, 0)))

                case "(":
                    _ascii_keys: str = ""

                    while char != ")":
                        _ascii_keys += char

                        ip += 1
                        if (ret := check_inc_ip("No ASCII keys end")) is not None:
                            return ret
                        char = keys[ip]

                    _ascii_keys = _ascii_keys[1:]

                    results.extend(
                        tuple((ord(c), state) for c in _ascii_keys for state in (1, 0))
                    )

                case "\\":
                    ip += 1
                    if (
                        ret := check_inc_ip("! is missing a special key character")
                    ) is not None:
                        return ret
                    char = keys[ip]

                    if char not in GUAC_KEYS_SPECIAL_MAPPING["escape"]:
                        return f"Invalid special key char: {char!r}"

                    results.append((GUAC_KEYS_SPECIAL_MAPPING["escape"][char], 1))

                case "!":
                    ip += 1
                    if (
                        ret := check_inc_ip("! is missing a special key character")
                    ) is not None:
                        return ret
                    char = keys[ip]

                    if char not in GUAC_KEYS_SPECIAL_MAPPING["escape"]:
                        return f"Invalid special key char: {char!r}"

                    results.append((GUAC_KEYS_SPECIAL_MAPPING["escape"][char], 0))

                case "{":
                    _repeat_ammount: str = ""
                    _repeat_ammount_ip: int = ip
                    _repeat_hit_group: bool = False

                    while char != "}":
                        if char == ":" and not _repeat_hit_group:
                            _repeat_hit_group = True

                        if (
                            not char.isnumeric()
                            and ip != _repeat_ammount_ip
                            and char != ":"
                            and not _repeat_hit_group
                        ):
                            return f"Invalid character in repeat: {char!r}"

                        _repeat_ammount += char

                        ip += 1
                        if (ret := check_inc_ip("No repeat end")) is not None:
                            return ret
                        char = keys[ip]

                    _repeat_ammount = _repeat_ammount[1:]

                    repeat_groups: List = _repeat_ammount.split(":")

                    if len(repeat_groups) < 2:
                        repeat_groups.append(1)

                    repeat_groups = list(map(int, repeat_groups))

                    repeat_group: List[Tuple[int, int]] = results[-repeat_groups[0] :]

                    for _ in range(repeat_groups[1]):
                        results.extend(repeat_group)

                case "|":
                    ip += 1
                    if (
                        ret := check_inc_ip("| is missing a special key character")
                    ) is not None:
                        return ret
                    char = keys[ip]

                    if char not in GUAC_KEYS_SPECIAL_MAPPING["escape"]:
                        return f"Invalid special key char: {char!r}"

                    results.extend(
                        (GUAC_KEYS_SPECIAL_MAPPING["escape"][char], state)
                        for state in (1, 0)
                    )

                case "<":
                    _keycode: str = ""
                    _keycode_ip: int = ip
                    _keycode_hit_state: bool = False

                    while char != ">":
                        if char == ":" and not _keycode_hit_state:
                            _keycode_hit_state = True

                        if (
                            not char.isnumeric()
                            and ip != _keycode_ip
                            and char != ":"
                            and not _keycode_hit_state
                        ):
                            return f"Invalid character in manual character: {char!r}"

                        _keycode += char

                        ip += 1
                        if (ret := check_inc_ip("No keycpde end")) is not None:
                            return ret
                        char = keys[ip]

                    _keycode = _keycode[1:]

                    keycodes: List = _keycode.split(":")

                    if len(keycodes) < 2:
                        keycodes.append(1)

                    results.append(tuple(map(int, keycodes)))  # type: ignore
        else:
            results.extend(
                (
                    (ord(char), 1),
                    (ord(char), 0),
                )
            )

        ip += 1

    GUAC_CACHE["guac-keys"][keys] = results

    return results


def paste(content: str, no_content_msg: str) -> Union[str, Tuple[None, str]]:
    if not content:
        return None, guac_msg("chat", no_content_msg)

    burl: str = "https://dpaste.com/api/v2/"

    pid = requests.post(
        burl,
        data={"content": content},
    )

    if not pid.ok:
        log(f"Failed to POST to {burl!r}")
        return None, guac_msg("chat", f"failed to POST to pastebin (code {pid.status_code})")

    return pid.text


def reset_authkey() -> None:
    AUTH["key"] = gen_key()
    log(f"New auth key: {AUTH['key']}")


def create_wh(url: str) -> dw.DiscordWebhook:
    return dw.DiscordWebhook(
        url=url,
        rate_limit_retry=True,
    )


def random_embed(url: str, title: str, content: str) -> dw.DiscordWebhook:
    wh = create_wh(url)
    _chatlog: str = "\n".join(STATE["chatlog"])

    wh.add_embed(
        dw.DiscordEmbed(
            title=title,
            description=f"""{content}

Chatlog: {paste(_chatlog, 'No chatlog')}""",
            color="%06x" % RANDOM.randint(0, 0xFFFFFF),
        )
    )

    return wh


def reload_config() -> None:
    log("Reloading config")

    with open(CONFIG_FILE, "r") as cfg:
        CONFIG.update(json.load(cfg))


def save_config(reload: bool = True) -> None:
    log("Saving config")

    with open(CONFIG_FILE, "w") as cfg:
        json.dump(CONFIG, cfg, indent=4)

    if reload:
        reload_config()


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


def dump_log(time: str) -> str:
    if not os.path.exists(CONFIG["logs-dir"]):
        log(f"Making {CONFIG['logs-dir']!r} directory")
        os.mkdir(CONFIG["logs-dir"])

    _log_file: str = os.path.join(
        CONFIG["logs-dir"],
        f"{STATE['vm']}-{''.join(c.replace(' ', '-') for c in time if c not in special_characters)}.log",
    )

    log(f"Dumping chatlog to {_log_file!r}")

    with open(
        _log_file,
        "w",
    ) as chatlog:
        chatlog.write("\n".join(STATE["chatlog"]))

    return chatlog.name


def generate_time_str() -> str:
    _utc: datetime = datetime.now(tz=timezone.utc)

    return datetime.strftime(
        _utc, f"{_utc.timestamp()} UNIX / %Y-%m-%d %H:%M:%S (%f microseconds) UTC"
    )


def chatlog_entry(message: str, user: str, header: Optional[str] = None) -> None:
    _time: str = generate_time_str()

    if len(STATE["chatlog"]) > CONFIG["chatlog-limit"]:
        if CONFIG["autodump-chatlogs"]:
            dump_log(_time)

        STATE["chatlog"].clear()

    STATE["chatlog"].append(
        f"\n{(str(header) + ' ') if header is not None else ''}\
{user!r} @ {_time}: \
{message}"
    )


def check_impersonation(user: str) -> Optional[str]:
    _special: tuple[str, str] = (CONFIG["bot-name"], CONFIG["user-name"])
    user = user.lower()

    if (
        user not in CONFIG["not-impersonators"]
        and user
        and any([special in user.lower() for special in _special])
        and user not in _special
    ):
        log(f"Found impersonator: {user!r}")

        chatlog_entry("Found impersonator", user, "IMPERSONATOR")

        CONFIG["impersonators"].append(user)
        save_config()

        return guac_msg("chat", f"Found impersonator: {user!r}")

    return None


class CommandParser:
    @staticmethod
    def cmd_hi(user: str, args: List[str]) -> str:
        """Noauth command, says hello to the user
        Syntax: hi"""

        return guac_msg("chat", f"Hello, @{user} :}}")

    @staticmethod
    def cmd_log(user: str, args: List[str]) -> str:
        """Noauth command, authenticates the user
        Syntax: log <me|user> <in|out> <auth key>"""

        if len(args) < 3:
            return guac_msg("chat", "Uhh, I need <me|user> <in|out> <auth key>")

        if args[-1] != AUTH["key"]:
            return guac_msg("chat", f"@{user} your auth key is invalid lmao")

        reset_authkey()

        auth_user: str = args[0]
        if args[0] == "me":
            auth_user = user

        if auth_user in CONFIG["ignored"]:
            return guac_msg("chat", f"{auth_user!r} is ignored for a reason :|")

        if args[1] == "in":
            if auth_user in AUTH["users"]:
                return guac_msg("chat", f"{auth_user} is already authenticated")

            AUTH["users"].add(auth_user)
        elif args[1] == "out":
            if auth_user not in AUTH["users"]:
                return guac_msg("chat", f"{auth_user} is not authenticated")

            AUTH["users"].add(auth_user)
        else:
            return guac_msg("chat", f"How do I log {args[1]!r} a person out???")

        return guac_msg("chat", f"@{auth_user} you have been logged {args[1]}")

    @staticmethod
    def cmd_getkey(user: str, args: List[str]) -> str:
        """Noauth command, authenticates the user
        Syntax: getkey"""

        log(f"{user!r} requested auth key: {AUTH['key']}")
        return guac_msg("chat", f"@{user} check the console for the key")

    @staticmethod
    def cmd_whoami(user: str, args: List[str]) -> str:
        """Auth command, authenticates the user
        Syntax: getkey"""

        return guac_msg("chat", f"You are {user} :D")

    @staticmethod
    def cmd_die(user: str, args: List[str]) -> str:
        """Auth command, exists the server
        Syntax: die"""

        STATE["run"] = False

        if CONFIG["bye-message"]:
            return guac_msg("chat", CONFIG["bye-message"])

        return guac_msg("nop")

    @staticmethod
    def cmd_savecfg(user: str, args: List[str]) -> str:
        """Auth command, saves the config
        Syntax: savecfg"""

        save_config()
        return guac_msg("chat", f"{CONFIG_FILE!r} saved")

    @staticmethod
    def cmd_note(user: str, args: List[str]) -> Union[Tuple[str, ...], str]:
        """Auth command, makes a note and then saves the config
        Syntax: note <name> <content...>"""

        if len(args) < 2:
            return guac_msg(
                "chat", "Huh? I kinda need the <name> and the <conrent> of the note"
            )

        existed: bool = args[0] in CONFIG["notes"]
        old_note: str = ""

        if existed:
            old_note = CONFIG["notes"][args[0]]

        CONFIG["notes"][args[0]] = " ".join(args[1:])

        save_config()

        if existed:
            log(f"Edited note {args[0]!r} -- {old_note!r}")

            return (
                guac_msg("chat", f"Lol, done, note {args[0]!r} edited ;)"),
                guac_msg("chat", f"> {old_note}"),
            )

        return guac_msg("chat", f"Note {args[0]!r} saved <3")

    @staticmethod
    def cmd_get(user: str, args: List[str]) -> str:
        """Noauth command, gets a note
        Syntax: get <name>"""

        if not args:
            return guac_msg("chat", "What note do you need lol")

        if args[0] not in CONFIG["notes"]:
            return guac_msg("chat", "That's not a note... zamn")

        return guac_msg("chat", f"> {CONFIG['notes'][args[0]]}")

    @staticmethod
    def cmd_del(user: str, args: List[str]) -> str:
        """Auth command, deletes a note
        Syntax: del <name>"""

        if not args:
            return guac_msg("chat", "What note do you want me to rm -rf?")

        if args[0] not in CONFIG["notes"]:
            return guac_msg("chat", "That's not note, such shame")

        del CONFIG["notes"][args[0]]

        save_config()
        return guac_msg("chat", f"Note {args[0]!r} deleted, sad to see it go kinda")

    @staticmethod
    def cmd_notes(user: str, args: List[str]) -> str:
        """Auth command, lists the notes
        Syntax: notes"""

        pid = paste(
            "\n".join(f"* {note}" for note in CONFIG["notes"]),
            f"@{user} No notes to show you, want some tea though?",
        )

        if pid[0] is None:
            return pid[1]

        return guac_msg("chat", f"@{user} Here's a list of notes: {pid}")

    @staticmethod
    def cmd_ignore(user: str, args: List[str]) -> str:
        """Auth command, ignores a user
        Syntax: ignore <user>"""

        if not args:
            return guac_msg("chat", "Who do I even ignore lmao???????")

        if args[0] in AUTH["users"]:
            return guac_msg(
                "chat",
                "Yeah... no, I don't think ignoring authenticated users is a good idea",
            )

        if args[0] in CONFIG["ignored"]:
            return guac_msg("chat", "You want me to ignore an already ignored user?")

        CONFIG["ignored"].append(args[0])
        save_config()

        return guac_msg(
            "chat",
            f"@{args[0]}'s commands will be ignored from now on lmao, imagine",
        )

    @staticmethod
    def cmd_acknowledge(user: str, args: List[str]) -> str:
        """Auth command, acknowledges a user
        Syntax: acknowledge <user>"""

        if not args:
            return guac_msg("chat", "Hm? Who do you want me to acknowledge?")

        if args[0] not in CONFIG["ignored"]:
            return guac_msg(
                "chat",
                "They're not ignored lol, you trying to say something? :eyes:",
            )

        CONFIG["ignored"].remove(args[0])
        save_config()

        return guac_msg(
            "chat",
            f"@{args[0]}'s commands will be not ignored from now on :)",
        )

    @staticmethod
    def cmd_ignored(user: str, args: List[str]) -> str:
        """Auth command, lists the ignored users
        Syntax: ignored"""

        pid = paste(
            "\n".join(f"* {ignored}" for ignored in CONFIG["ignored"]),
            f"@{user} No users being ignored, which is a good thing I presume?",
        )

        if pid[0] is None:
            return pid[1]

        return guac_msg("chat", f"@{user} Here's ur a list of ignored ppl heh: {pid}")

    @staticmethod
    def cmd_insult(user: str, args: List[str]) -> str:
        """Noauth command, insults a specified user
        Syntax: insult <user>"""

        if not args:
            return guac_msg("chat", "I like.. need the <user> to insult them lmao")

        if args[0] == "me":
            args[0] = user

        if args[0] == CONFIG["user-name"] and user == CONFIG["user-name"]:
            return guac_msg(
                "chat",
                f"@{args[0]} I would never insult you <3",
            )

        if args[0] == CONFIG["bot-name"]:
            return guac_msg(
                "chat",
                f"Hey, @{user}, do you really think I suck? I have feelings too :(",
            )

        if args[0] == CONFIG["user-name"]:
            return guac_msg(
                "chat",
                f"Come on, @{user}, {CONFIG['user-name']} is my owner, why would I insult them?",
            )

        return guac_msg(
            "chat",
            " ".join(
                f"@{args[0]} you are a {' '.join(RANDOM.choice(CONFIG['insults'][_from]) for _from in ('descriptors', 'adjectives', 'nouns'))}".split()
            ),
        )

    @staticmethod
    def cmd_revokey(user: str, args: List[str]) -> str:
        """Noauth command, revoke current auth key
        Syntax: revokey"""

        reset_authkey()
        return guac_msg("chat", f"@{user} the current auth key has been revoked")

    @staticmethod
    def cmd_alias(user: str, args: List[str]) -> str:
        """Auth command, aliases a command to a command
        Syntax: alias <name> <content...>"""

        if len(args) < 2:
            return guac_msg(
                "chat",
                f"@{user} O, You made a mistake lmao, gimme the <name> AND the <content...>",
            )

        if args[0] in CONFIG["aliases"]:
            return guac_msg(
                "chat",
                f"@{user} alias {args[0]!r} already exists :(",
            )

        CONFIG["aliases"][args[0]] = " ".join(args[1:])
        save_config()

        return guac_msg("chat", f"Alias {args[0]!r} saved")

    @staticmethod
    def cmd_unalias(user: str, args: List[str]) -> str:
        """Auth command, unaliases an alias
        Syntax: unalias <name>"""

        if not args:
            return guac_msg(
                "chat",
                f"@{user} Hm? What do I need to unalias?",
            )

        if args[0] not in CONFIG["aliases"]:
            return guac_msg(
                "chat",
                f"@{user} I'm like... 101% sure alias {args[0]!r} doesn't exist",
            )

        del CONFIG["aliases"][args[0]]
        save_config()

        return guac_msg("chat", f"Unaliased {args[0]!r}")

    @staticmethod
    def cmd_aliases(user: str, args: List[str]) -> str:
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
            return pid[1]

        return guac_msg("chat", f"@{user} Here's a list of your aliases: {pid}")

    @classmethod
    def cmd_report(cls, user: str, args: List[str]) -> str:
        """Auth command, reports a user
        Syntax: report <user> <reason>"""

        if not CONFIG["report-webhook-url"]:
            return guac_msg(
                "chat",
                f"@{user} please ask the owner ({CONFIG['user-name']}) to set reports up",
            )

        if len(args) < 2:
            return guac_msg(
                "chat",
                f"@{user} Who and for what do I report to admins/mods?",
            )

        _report_content: str = " ".join(args[1:])
        _report_title: str = (
            f"Report from {user!r} about {args[0]!r} in {STATE['vm']!r}"
        )

        # Note the user down

        cls.cmd_note(user, [f"forkie-{args[0]}", _report_content])
        cls.cmd_ignore(user, [args[0]])

        # Send off the report

        wh = random_embed(
            CONFIG["report-webhook-url"],
            _report_title,
            f"Reason: `{_report_content.replace('`', '  ')}`",
        )
        log(f"{_report_title}: {wh.execute()}")

        # Respond to user

        return guac_msg(
            "chat",
            f"Reported user @{args[0]} to admins/mods, imagine getting banned :skull:",
        )

    @staticmethod
    def cmd_sendkey(user: str, args: List[str]) -> str:
        """Noauth command, sends the auth key to the specified hook
        Syntax: sendkey"""

        if not CONFIG["authkey-webhook-url"]:
            return guac_msg(
                "chat",
                f"@{user} the config isn't set up properly to use sendkey, you forgot a thing",
            )

        wh = random_embed(
            CONFIG["authkey-webhook-url"],
            f"Auth key request by {user!r} in {STATE['vm']!r}",
            f"||{AUTH['key']}||",
        )

        log(f"Sent key to discord webhook: {wh.execute()}")

        return guac_msg(
            "chat",
            f"@{user} the key has been sent",
        )

    @staticmethod
    def cmd_chatlog(user: str, args: List[str]) -> str:
        """Auth command, gets current chatlog
        Syntax: chatlog"""

        pid = paste(
            "\n".join(STATE["chatlog"]),
            f"@{user} Chatlog is empty, lmao, how is that even possible???",
        )

        if pid[0] is None:
            return pid[1]

        return guac_msg(
            "chat",
            f"@{user} Current chatlog (limit: {CONFIG['chatlog-limit']}): {pid}",
        )

    @staticmethod
    def cmd_dumplog(user: str, args: List[str]) -> str:
        """Auth command, dumps current chatlog
        Syntax: dumplog"""

        _dumplog_filename: str = dump_log(f"{user} {generate_time_str()}")

        return guac_msg(
            "chat",
            f"@{user} Dumped to {_dumplog_filename}",
        )

    @staticmethod
    def cmd_say(user: str, args: List[str]) -> str:
        """Auth command, says whatever you say it to say
        Syntax: dumplog"""

        if not args:
            return guac_msg("chat", f"Eh, you do it @{user}")

        return guac_msg(
            "chat",
            " ".join(args),
        )

    @staticmethod
    def cmd_searchnote(user: str, args: List[str]) -> str:
        """Noauth command, searches for a note
        Syntax: searchnote <search>"""

        if not args:
            return guac_msg("chat", f"@{user} Gimme a query to find a note")

        query: str = " ".join(args)

        for note in CONFIG["notes"]:
            if query in note:
                return guac_msg("chat", f"@{user} Found note: {note}")

        return guac_msg("chat", f"@{user} No notes that matches this found")

    @staticmethod
    def cmd_searchalias(user: str, args: List[str]) -> str:
        """Noauth command, searches for an alias
        Syntax: searchalias <search>"""

        if not args:
            return guac_msg("chat", f"@{user} ??huh?? What alias should I look for?")

        query: str = " ".join(args)

        for alias in CONFIG["aliases"]:
            if query in alias:
                return guac_msg("chat", f"@{user} Found alias: {alias}")

        return guac_msg("chat", f"@{user} No aliases matches your query")

    @staticmethod
    def cmd_impersonator(user: str, args: List[str]) -> str:
        """Auth command, marks a user as an impersonator
        Syntax: impersonator <user>"""

        if not args:
            return guac_msg("chat", f"@{user} Whos an impersonator")

        if args[0] in (CONFIG["bot-name"], CONFIG["user-name"]):
            return guac_msg("chat", f"@{user} I doubt lmao")

        CONFIG["impersonators"].append(args[0])
        return guac_msg("chat", f"@{user} Yep. added {args[0]!r} as an impersonator")

    @staticmethod
    def cmd_notimpersonator(user: str, args: List[str]) -> str:
        """Auth command, marks a user as not an impersonator
        Syntax: notimpersonator <user>"""

        if not args:
            return guac_msg("chat", f"@{user} Whos an impersonator")

        if args[0] in (CONFIG["bot-name"], CONFIG["user-name"]):
            return guac_msg("chat", f"@{user} Yeah. Lol")

        if (
            args[0] in CONFIG["not-impersonators"]
            and args[0] not in CONFIG["impersonators"]
        ):
            return guac_msg(
                "chat", f"@{user} {args[0]!r} isn't marked as an impersonator"
            )

        if args[0] in CONFIG["impersonators"]:
            CONFIG["impersonators"].remove(args[0])

        if args[0] not in CONFIG["not-impersonators"]:
            CONFIG["not-impersonators"].append(args[0])

        return guac_msg(
            "chat", f"@{user} {args[0]!r} is now marked as not an impersonator"
        )

    @staticmethod
    def cmd_turn(user: str, args: List[str]) -> str:
        """Auth command, takes turn
        Syntax: turn"""

        return guac_msg("turn")

    @staticmethod
    def cmd_keys(user: str, args: List[str]) -> Union[Tuple[str, ...], str]:
        """Auth command, types a supplied key combo
        Syntax: keys <combo>"""

        if not args:
            return guac_msg(f"@{user} ??? What, what do I type, like? Huh?")

        keys: Union[List[Tuple[int, int]], str] = parse_guac_keys(" ".join(args))

        if type(keys) is str:
            return guac_msg("chat", f"@{user} {keys}")

        STATE["sleep"] = 0.04
        return tuple(guac_msg("key", str(code), str(state)) for code, state in keys)  # type: ignore

    @staticmethod
    def cmd_endturn(user: str, args: List[str]) -> str:
        """Auth command, ends turn
        Syntax: endturn"""

        return guac_msg("turn", "0")

    @staticmethod
    def cmd_skeys(user: str, args: List[str]) -> str:
        """Auth command, lists the keys saved
        Syntax: skeys"""

        pid = paste(
            "\n".join(
                f"* {key_name} ({key})" for key_name, key in CONFIG["keys"].items()
            ),
            f"@{user} No key combos saved so... what do we do?",
        )

        if pid[0] is None:
            return pid[1]

        return guac_msg("chat", f"@{user} Here's a list of keys: {pid}")

    @staticmethod
    def cmd_skey(user: str, args: List[str]) -> str:
        """Auth command, save a key combo
        Syntax: skey <name> <combo>"""

        if len(args) < 2:
            return guac_msg(
                "chat", f"@{user} I need both the name of the key combo and the content"
            )

        CONFIG["keys"][args[0]] = " ".join(args[1:])
        save_config()

        return guac_msg("chat", f"@{user} Key combo {args[0]!r} saved")

    @classmethod
    def cmd_ikey(cls, user: str, args: List[str]) -> Union[str, Tuple[str, ...]]:
        """Auth command, invoke a key combo
        Syntax: ikey <combo_name>"""

        if not args:
            return guac_msg("chat", f"@{user} Gimme the key combo name")

        if args[0] not in CONFIG["keys"]:
            return guac_msg("chat", f"@{user} Couldn't find {args[0]!r} :shrug:")

        return cls.cmd_keys(user, [CONFIG["keys"][args[0]]])

    @staticmethod
    def cmd_reloadcfg(user: str, args: List[str]) -> str:
        """Auth command, reload config
        Syntax: reloadcfg"""

        reload_config()
        return guac_msg("chat", f"Configuration {CONFIG_FILE!r} reloaded")

    @staticmethod
    def cmd_dkey(user: str, args: List[str]) -> str:
        """Auth command, delete a key combo
        Syntax: dkey <combo_name>"""

        if not args:
            return guac_msg("chat", f"@{user} ")

        if args[0] not in CONFIG["keys"]:
            return guac_msg("chat", f"@{user} Won't delete {args[0]!r} Reason: yes")

        del CONFIG["keys"][args[0]]
        save_config()

        return guac_msg("chat", f"@{user} Deleted {args[0]!r}")


class MessageParser:
    @staticmethod
    def type_nop(content: List[str]) -> str:
        return guac_msg("nop")

    @classmethod
    def type_chat(cls, content: List[str]) -> Union[str, Tuple[str, ...]]:
        str_msg: str = html_unescape(" ".join(content[1:]))
        user: str = content[0].strip()

        if user and user != CONFIG["bot-name"]:
            chatlog_entry(str_msg, user)

        if user in CONFIG["ignored"]:
            return cls.type_nop(content)

        if user.lower() in CONFIG["impersonators"] and user not in AUTH["users"]:
            return guac_msg(
                "chat", f"User {user} is an impersonator. Do not trust them."
            )

        if user == "Mr. Ware" and "@Emperor Palpatine is not the senate" in str_msg:
            log(f"{user} bot is lying again smh")
            return guac_msg("chat", f"@{user} Yes he is >:(")

        if len(content) > 3 or not user or user == CONFIG["bot-name"]:
            return cls.type_nop(content)

        if content[1].lower().strip() in (
            f"@{CONFIG['user-name']}",
            CONFIG["user-name"],
        ):
            if user == CONFIG["user-name"]:
                return cls.type_nop(content)

            log(f"{user!r} mentioned the owner without any conrext")
            return guac_msg("chat", f"@{user} smh whattttttttttttt")

        command: List[str] = list(
            map(
                lambda s: s.replace("`", " "),
                str_msg.split()[1:],
            )
        )
        _dad_joke_im: str = content[1].lower().split(" ", 1)[0]

        def _check_command() -> Optional[str]:
            if not command:
                return cls.type_nop(content)

            return None

        if (
            _dad_joke_im in ("i&#x27;m", "im")
            or _dad_joke_im == "i"
            and command
            and command[0].lower() == "am"
        ):
            if (_ret := _check_command()) is not None:
                return _ret

            if command[0].lower() == "am":
                command = command[1:]

                if (_ret := _check_command()) is not None:
                    return _ret

            _dad_joke_who: str = " ".join(command)
            _special: tuple[str, str] = (CONFIG["bot-name"], CONFIG["user-name"])

            if (
                _dad_joke_who in _special or _dad_joke_who[1:] in _special
            ) and user != _dad_joke_who.strip():
                log(
                    f"User {user!r} said they're from special users ({_dad_joke_who!r})"
                )
                return guac_msg("chat", f"@{user} Yeah I doubt lmao")

            log(f"User {user!r} invoked a dad joke: {_dad_joke_who!r}")
            return guac_msg("chat", f"Hi {_dad_joke_who}, I'm {CONFIG['bot-name']} :)")

        _bot_mention: str = f"@{CONFIG['bot-name']}"

        if content[1].startswith(_bot_mention) and not len(command):
            log(f"{user!r} mentioned the bot without a command")
            return guac_msg("chat", f"@{user} Huh? What do you want lol")

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
                                f"@{CONFIG['bot-name']} {CONFIG['aliases'][command[0]]} \
{' '.join(str_msg.split(' ')[2:])}".strip(),
                            ]
                        )
                    except RecursionError:
                        log(f"Recursive alias detected: {command[0]!r}")

                        return guac_msg(
                            "chat", "ZAMN! Your alias is *extremely* recursive"
                        )

                return guac_msg("chat", f"Lmao what even is {command[0]!r}?")

            if (cmd_handler.__doc__ or "").strip().startswith("Noauth"):
                return cmd_handler(user, command[1:])

            if user not in AUTH["users"]:
                return guac_msg("chat", f"Hey {user!r}, you are not authenticated :(")

            return cmd_handler(user, command[1:])

        return cls.type_nop(content)

    @classmethod
    def type_adduser(cls, content: List[str]) -> str:
        if ret := check_impersonation(content[1]):
            return ret

        if not content[1].startswith("scrot"):
            chatlog_entry("Joined", content[1], "JOIN")

            if RANDOM.randint(0, 1000) == 420:
                log(f"Welcoming {content[1]!r}")
                return guac_msg("chat", f"Welcome, {content[1]!r}. How are you?")

        return cls.type_nop(content)

    @classmethod
    def type_remuser(cls, content: List[str]) -> str:
        if not content[1].startswith("scrot"):
            chatlog_entry("Left", content[1], "LEAVE")

            if content[1] in AUTH["users"]:
                log(f"Logging {content[1]!r} out")
                AUTH["users"].remove(content[1])

            if RANDOM.randint(0, 1000) == 69:
                log(f"Saying goodbye to {content[1]!r}")
                return guac_msg("chat", f"Goodbye, {content[1]!r}. Have a nice day")

        return cls.type_nop(content)

    @classmethod
    def type_rename(cls, content: List[str]) -> str:
        if ret := check_impersonation(content[2]):
            return ret

        chatlog_entry(f"{content[1]!r} -> {content[2]!r}", content[1], "RENAME")

        if content[2] in AUTH["users"]:
            log(f"User has renamed themselves so logging {content[2]!r} out")
            AUTH["users"].remove(content[2])

        return cls.type_nop(content)

    @classmethod
    def type_turn(cls, content: List[str]) -> str:
        if len(content) > 2:
            chatlog_entry(
                f"Took turn for {int(content[0]) / 1000} seconds", content[2], "TURN"
            )

        return cls.type_nop(content)

    @classmethod
    def type_vote(cls, content: List[str]) -> str:
        chatlog_entry(
            f"{VOTE_STATES.get(int(content[0])) or 'Unknown vote type'}: {' '.join(content)}",
            "Server",
            "RESET",
        )
        return cls.type_nop(content)


async def main() -> int:
    """Entry/main function"""

    if not os.path.isfile(CONFIG_FILE):
        log(f"Making default config in {CONFIG_FILE!r}")
        save_config(False)
    else:
        reload_config()

    log("Preparing impersonators list")
    CONFIG["impersonators"] = list(map(str.lower, CONFIG["impersonators"]))
    save_config()

    STATE["vm"] = CONFIG["vm"]

    if len(sys.argv) > 1:
        STATE["vm"] = sys.argv[1]

    s: aiohttp.ClientSession = aiohttp.ClientSession()
    url: str = f"ws://0.tcp.in.ngrok.io:11457/collab-vm/{STATE['vm']}/"

    log(f"Connecting to {url!r}")

    async with s.ws_connect(
        url,
        protocols=["guacamole"],
        origin="http://0.tcp.in.ngrok.io:11457/",
        autoclose=False,
        autoping=False,
    ) as ws:
        await ws.send_str(guac_msg("rename", CONFIG["bot-name"]))
        await ws.send_str(guac_msg("connect", STATE["vm"]))

        log("Connected")

        if CONFIG["init-message"].strip():
            await ws.send_str(guac_msg("chat", CONFIG["init-message"]))

        reset_authkey()
        AUTH["users"].clear()

        async for msg in ws:
            parsed_msg: Optional[List[str]] = unguac_msg(msg.data)

            if parsed_msg is None:
                ws.send_str(  # type: ignore
                    guac_msg("chat", f"The guac parser failed on message: {msg!r}")
                )
                continue

            result: Union[str, Tuple[str]] = (
                getattr(MessageParser, f"type_{parsed_msg[0]}", None)
                or MessageParser.type_nop
            )(parsed_msg[1:])

            if type(result) is str:
                result = (result,)

            for send_msg in result:
                if STATE["sleep"]:
                    await asyncio.sleep(STATE["sleep"])

                await ws.send_str(send_msg)

            STATE["sleep"] = 0

            if not STATE["run"]:
                log("Run state was set to false")
                await ws.close()
                break

    save_config(False)

    if CONFIG["autodump-chatlogs"]:
        log(f"Dumped log: {dump_log(generate_time_str())!r}")

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
            time.sleep(30)

    sys.exit(ret)
