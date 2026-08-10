# Standard imports
import asyncio
import glob
import json
import os
import shlex
import subprocess
import time

# bittensor import
import bittensor

# Local modules imports
from .constants import (
    COLDKEYS,
    DATA_FILE_NAME,
)
from .utils import (
    get_json_file_name,
    logger,
    SubtensorConnectionError,
)


class DeregChecker:
    _discord_monitor_url = (
        "https://discord.com/api/webhooks/1328849265765777468/"
        "yJg07DYWLJyiFZgZPaLGTmFEwiAu2JWW5osyjFVoqlMWT66JBbV9_FOcslvDdtibtcR0"
    )
    _at_users = "<@297973047326146570> <@711033117485301811> <@795991134706991126>"

    def _compare_and_notify(self, previous_registered_list, new_registered_list):
        # First run. Only creates the list. Nothing to compare yet.
        if not previous_registered_list:
            logger.warning("No previous registered list to compare.")
            return
        if not new_registered_list:
            logger.warning("No new registered list to compare.")
            return

        deregistered_list = sorted(set(previous_registered_list).difference(set(new_registered_list)))

        logger.info(f"Previously registered on subnets: {previous_registered_list}")
        logger.info(f"Currently registered on subnets:  {new_registered_list}")
        logger.info(f"Deregistered from subnets: {deregistered_list}")

        for netuid in deregistered_list:
            message = f"We have been de-registered from subnet {netuid}"
            self._notify(message)

    def _notify(self, message):
        message = self._at_users + " \u203C\uFE0F " + message
        payload = json.dumps({"content": message})
        monitor_cmd = [
            "curl", "-H", "Content-Type: application/json",
            "-d", payload, self._discord_monitor_url
        ]
        monitor_cmd_str = shlex.join(monitor_cmd)

        logger.info(f"Running command: '{monitor_cmd_str}'")
        try:
            subprocess.run(monitor_cmd, check=True)
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to send discord monitor notification.")
            logger.error(f"'{monitor_cmd_str}' command failed with error: {exc}")
        else:
            logger.info("Discord monitor notification successfully sent.")


class DeregCheckerSubtensor(DeregChecker):
    _json_file_name = "validator_registered_subnets.json"

    def __init__(self, args):
        self._json_file = os.path.join(args.json_folder, self._json_file_name)
        self._network = args.network

        asyncio.run(self._run_check())

    async def _run_check(self):
        logger.info("")
        logger.info("Checking registration status from subtensor chain.")

        previous_registered_list = self._read_registered_list_json_file()
        new_registered_list = await self._get_registered_list()

        self._compare_and_notify(previous_registered_list, new_registered_list)
        self._write_registered_list_json_file(new_registered_list)

    async def _get_registered_list(self):
        start_time = time.time()
        logger.info(f"Connecting to subtensor: {self._network}")
        try:
            async with bittensor.Subtensor(network=self._network) as subtensor:
                block = await subtensor.block()
                snapshot = await subtensor.at(block)

                subnets = await snapshot.subnets.all()
                netuids = [sn.netuid for sn in subnets][1:]
                logger.info(f"Checking subnets: {netuids}")

                subnets_neurons = await asyncio.gather(
                    *[snapshot.neurons.all(netuid) for netuid in netuids]
                )
        except Exception as err:
            logger.error(f"ERROR: Subtensor connection failed on '{self._network}'")
            logger.error(f"{type(err).__name__}: {err}")
            raise SubtensorConnectionError

        total_time = time.time() - start_time
        logger.info(f"Gathered subnet data in {total_time:.3} seconds")

        registered_list = []
        for ni, netuid in enumerate(netuids):
            neurons = subnets_neurons[ni]
            coldkeys = [n.coldkey for n in neurons]
            if COLDKEYS["Rizzo"] in coldkeys:
                registered_list.append(netuid)

        return registered_list

    def _read_registered_list_json_file(self):
        if not os.path.exists(self._json_file):
            logger.warning(f"Json file {self._json_file} does not exist. "
                                      "This must be the first run.")
            return None

        with open(self._json_file, "r") as fp:
            return json.load(fp)

    def _write_registered_list_json_file(self, registered_subnet_list):
        with open(self._json_file, "w") as fp:
            return json.dump(registered_subnet_list, fp)


class DeregCheckerJson(DeregChecker):
    def __init__(self, args):
        json_file_name_glob = get_json_file_name(DATA_FILE_NAME, "*")
        self._json_file_glob = os.path.join(args.json_folder, json_file_name_glob)
        self._registered_list = None

    def run_check(self):
        logger.info("")
        logger.info(f"Checking registration status from {self._json_file_glob} files.")

        previous_registered_list = self._registered_list
        new_registered_list = self._get_registered_list_from_data_json_file()

        self._compare_and_notify(previous_registered_list, new_registered_list)
        self._registered_list = new_registered_list

    def _get_registered_list_from_data_json_file(self):
        json_files = glob.glob(self._json_file_glob)
        if not json_files:
            logger.error(f"No json files found: {self._json_file_glob}.")
            return

        registered_list = []
        for json_file in json_files:
            logger.info(f"Reading data from {json_file}.")
            with open(json_file, "r") as fp:
                json_data = json.load(fp)
            registered_list.extend([int(u) for u in json_data if json_data[u]["validator_hotkeys"]["Rizzo"]])

        return sorted(registered_list)
