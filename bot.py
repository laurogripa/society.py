import re
import time
import niobot
import logging
import society
import messages
import asyncio
import os
from dotenv import load_dotenv
from niobot import Context, RoomMessage, RoomMessageText
from handle_upload import HandleUpload

load_dotenv()

room = os.getenv("MATRIX_ROOM")
matrix_access_token = os.getenv("MATRIX_TOKEN")
rpc_url = os.getenv("RPC_URL")
db_path = os.getenv("DB_PATH")
prefix = os.getenv("PREFIX")
loglevel = os.getenv("LOGLEVEL") or "INFO"
logging.getLogger()
logging.basicConfig(level=loglevel)
logging.info("Logging level: {}".format(loglevel))

soc = society.Society(rpc_url, db_path)

bot = niobot.NioBot(
    homeserver = "https://matrix.org",
    user_id = "@societybot:matrix.org",
    command_prefix = prefix,
    case_insensitive = False,
    owner_id = "@s3krit:fairydust.space"
)


async def new_period_message():
    candidate_period = soc.get_candidate_period()
    last_period = candidate_period.period
    first_run = True

    while True:
        candidate_period = soc.get_candidate_period()
        if candidate_period.period == "voting":
            logging.info("Blocks until end of voting period: {}".format(candidate_period.voting_blocks_left))
        else:
            logging.info("Blocks until end of claim period: {}".format(candidate_period.claim_blocks_left))
        if candidate_period.period != last_period and not first_run:
            # Period has changed. Send a message
            last_period = candidate_period.period
            candidates = soc.get_candidates()
            head = soc.get_head_address()
            defender_info = soc.get_defending()
            candidate_skeptic = soc.get_candidate_skeptic()

            message = messages.period_message(candidate_period, defender_info, candidates, head, candidate_skeptic, new_period=True)
            logging.info(message)
            await bot.send_message(room, message)
        first_run = False
        await asyncio.sleep(60)

async def get_info(address):
    info = soc.get_member_info(address)
    if info:
        response = ""
        for key in info:
            response += "* **{}**: {}\n".format(key.capitalize(), info[key])
        return response
    else:
        None

@bot.on_event("command_error")
async def on_command_error(ctx: Context, error: Exception):
    if isinstance(error, niobot.CommandArgumentsError):
        await ctx.respond("Invalid arguments: " + str(error))
    elif isinstance(error, niobot.CommandDisabledError):
        await ctx.respond("Command disabled: " + str(error))
    else:
        error = getattr(error, 'exception', error)
        await ctx.respond("Error: " + str(error))
        bot.log.error('command error in %s: %r', ctx.command.name, error, exc_info=error)

@bot.on_event("ready")
async def on_ready(_: niobot.SyncResponse):
    asyncio.create_task(new_period_message())

async def message_listener(room, event):
    if isinstance(event, RoomMessageText):
        pattern = f"([{re.escape(prefix)}|!]?upload.*)"
        match = re.search(pattern, event.body)
        if match:
            handle_upload = HandleUpload(bot, room, event)
            await handle_upload.handle(match.group(0), soc)

bot.add_event_callback(message_listener, RoomMessage)

@bot.command()
async def ping(ctx: Context):
    """Shows the roundtrip latency"""
    roundtrip = (time.time() * 1000 - ctx.event.server_timestamp)
    await ctx.respond("Pong! Took {:,.2f}ms".format(roundtrip))

@bot.command()
async def upload(ctx: Context, address: str, force_or_remove: str = None):
    """Upload PoI image to IPFS. Use `force` to overwrite an existing image or `remove` to delete it."""
    pass

bot.run(access_token=matrix_access_token)
