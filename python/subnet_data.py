# bittensor import
from bittensor.core.async_subtensor import AsyncSubtensor

# standart imports
import asyncio
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
import json
import numpy
import threading
import time


MIN_STAKE_THRESHOLD = 4000 # TODO - Need some way to verify this
                           # This is the value used by the taoyield site
MIN_VTRUST_THRESHOLD = 0.01
MAX_U_THRESHOLD = 100800 # 2 weeks


class SubnetDataBase:
    ValidatorData = namedtuple(
    "ValidatorData", [
        "netuid",
        "subnet_emission",
        "subnet_tempo",
        "num_total_validators",
        "num_valid_validators",
        "rizzo_stake_rank",
        "rizzo_emission",
        "rizzo_vtrust",
        "max_vtrust",
        "avg_vtrust",
        "min_vtrust",
        "rizzo_updated",
        "min_updated",
        "avg_updated",
        "max_updated",])

    def __init__(self, debug):
        self._debug = debug
        self._validator_data = {}

        # Gather the data for all given subnets
        self._get_subnet_data()

    @property
    def validator_data(self):
        return self._validator_data

    def _print_debug(self, message):
        if self._debug:
            print(message)


class SubnetData(SubnetDataBase):
    _rizzo_hotkey = "5F2CsUDVbRbVMXTh9fAzF9GacjVX7UapvRxidrxe7z8BYckQ"

    def __init__(self, netuids, network, threads, debug, other_hotkey=None):
        self._netuids = netuids
        self._network = network
        self._threads = threads
        self._other_hotkey = other_hotkey

        self._validator_data_lock = threading.Lock()

        super(SubnetData, self).__init__(debug)

    def to_dict(self):
        def serializable(value):
            if isinstance(value, numpy.float32):
                return float(value)
            if isinstance(value, numpy.int64):
                return int(value)
            return value

        data_dict = {}
        for netuid in self._validator_data:
            data = self._validator_data[netuid]
            data_dict[netuid] = dict(
                [(f, serializable(getattr(data, f))) for f in data._fields])
        return data_dict

    def _get_subnet_data(self):
        self._print_debug("\nGathering data")

        max_attempts = 5
        netuids = self._netuids
        for attempt in range(1, max_attempts+1):
            self._print_debug(f"\nAttempt {attempt} of {max_attempts}")
            if self._threads:
                # TODO - This could be way better now that it's using asyncio
                with ThreadPoolExecutor(max_workers=self._threads) as executor:
                    executor.map(self._get_validator_data, netuids)
            else:
                self._get_validator_data(netuids)

            # Get netuids missing data
            netuids = list(set(netuids).difference(set(self._validator_data)))
            if netuids:
                self._print_debug("\nFailed to gather data for subnets: "
                                 f"{', '.join([str(n) for n in netuids])}.")
            else:
                break

    def _get_validator_data(self, netuids):
        asyncio.run(self._async_get_validator_data(netuids))

    async def _async_get_validator_data(self, netuids):
        if type(netuids) != list:
            netuids = [netuids]

        # When threading, re-get subtensor for obtaining the updated values.
        # The subtensor object can't seem to handle multiple threads calling
        # the blocks_since_last_update() method at the same time.
        start_time = time.time()
        self._print_debug(f"\nObtaining data for subnets: {netuids}\n")

        async with AsyncSubtensor(network="archive") as subtensor:
            block = await subtensor.block
            metagraphs = await asyncio.gather(
                *[subtensor.metagraph(netuid=netuid, block=block) for netuid in netuids]
            )
            for i, netuid in enumerate(netuids):
                metagraph = metagraphs[i]
                self._get_data_from_metagraph(metagraph, netuid, block)

        total_time = time.time() - start_time
        self._print_debug(f"\nData gathered in {int(total_time)} seconds "
                          f"for subnets: {netuids}.")

    def _get_data_from_metagraph(self, metagraph, netuid, current_block):    
        # Get emission percentage for the subnet.
        subnet_emission = metagraph.emissions.tao_in_emission * 100

        # Get subnet tempo (used for determining bad Updated values)
        # subnet_tempo = subtensor.get_subnet_hyperparameters(netuid).tempo
        subnet_tempo = 360

        # A hack to be able to check how other validators are doing
        hotkey = self._other_hotkey or self._rizzo_hotkey

        # Get UID for Rizzo.
        try:
            rizzo_uid = metagraph.hotkeys.index(hotkey)
        except ValueError:
            rizzo_uid = None
            self._print_debug(
                "\nWARNING: Rizzo validator not running on subnet "
                f"{netuid}"
            )

        # Get Rizzo validator values
        if rizzo_uid is None:
            rizzo_emission = None
            rizzo_vtrust = None
            rizzo_updated = None
            rizzo_stake_rank = None
        else:
            rizzo_emission = metagraph.E[rizzo_uid]
            rizzo_vtrust = metagraph.Tv[rizzo_uid]
            rizzo_updated = current_block - metagraph.last_update[rizzo_uid]

            rizzo_stake = metagraph.S[rizzo_uid]
            rizzo_stake_rank = (
                len(metagraph.S) - sorted(metagraph.S).index(rizzo_stake))

        # Get all validator uids that have valid stake amount
        all_uids = [
            i for (i, s) in enumerate(metagraph.S)
            if i != rizzo_uid and s > MIN_STAKE_THRESHOLD
        ]
        num_total_validators = len(all_uids)

        # Get all validators that have proper VT and U
        valid_uids = [
            i for i in all_uids
            if (metagraph.Tv[i] > MIN_VTRUST_THRESHOLD)
            & (current_block - metagraph.last_update[i] < MAX_U_THRESHOLD)
        ]
        num_valid_validators = len(valid_uids)

        if rizzo_uid is not None:
            num_total_validators += 1
            if (
                rizzo_vtrust is not None and rizzo_vtrust > MIN_VTRUST_THRESHOLD
                and rizzo_updated is not None and rizzo_updated < MAX_U_THRESHOLD
            ):
                num_valid_validators += 1

        if not valid_uids:
            max_vtrust = None
            avg_vtrust = None
            min_vtrust = None
            min_updated = None
            avg_updated = None
            max_updated = None
        else:
            # Get min/max/average vTrust values.
            vtrusts = metagraph.Tv[valid_uids]
            max_vtrust = numpy.max(vtrusts)
            avg_vtrust = numpy.average(vtrusts)
            min_vtrust = numpy.min(vtrusts)

            # Get min/max/average Updated values.
            updateds = current_block - metagraph.last_update[valid_uids]
            min_updated = numpy.min(updateds)
            avg_updated = int(numpy.round(numpy.average(updateds)))
            max_updated = numpy.max(updateds)

        # Store the data.
        with self._validator_data_lock:
            self._validator_data[netuid] = self.ValidatorData(
                netuid=netuid,
                subnet_emission=subnet_emission,
                subnet_tempo=subnet_tempo,
                num_total_validators=num_total_validators,
                num_valid_validators=num_valid_validators,
                rizzo_stake_rank=rizzo_stake_rank,
                rizzo_emission=rizzo_emission,
                rizzo_vtrust=rizzo_vtrust,
                max_vtrust=max_vtrust,
                avg_vtrust=avg_vtrust,
                min_vtrust=min_vtrust,
                rizzo_updated=rizzo_updated,
                min_updated=min_updated,
                avg_updated=avg_updated,
                max_updated=max_updated,)


class SubnetDataFromWebServer(SubnetDataBase):
    def __init__(self, public_ip, port, username, password, debug):
        self._public_ip = public_ip
        self._port = port
        self._username = username
        self._password = password

        super(SubnetDataFromWebServer, self).__init__(debug)

    def _get_subnet_data(self):
        from bs4 import BeautifulSoup
        import requests

        subnets_data = {}

        main_url = f"http://{self._public_ip}:{self._port}"
        self._print_debug(f"Obtaining validator json data from: {main_url}")
        response = requests.get(main_url, auth=(self._username, self._password))
        if response.status_code != 200:
            self._print_debug("\nERROR: Failed to obtain validator json data."
                              f"\nurl: {main_url}"
                              f"\nstatus code: {response.status_code}"
                              f"\nreason: {response.reason}")
            return

        html_content = BeautifulSoup(response.content.decode(), features="html.parser")
        for li_tag in html_content.findAll("li"):
            json_file = li_tag.find("a").get("href")
            json_url = f"http://{self._public_ip}:{self._port}/{json_file}"
            self._print_debug(f"Updating validator json data with: {json_url}")
            response = requests.get(json_url, auth=(self._username, self._password))
            if response.status_code != 200:
                self._print_debug("\nERROR: Failed to obtain validator json data."
                                  f"\nurl: {json_url}"
                                  f"\nstatus code: {response.status_code}"
                                  f"\nreason: {response.reason}")
                return
            
            subnets_data.update(response.json())

        for subnet in subnets_data.values():
            self._validator_data[subnet["netuid"]] = self.ValidatorData(
                netuid=subnet["netuid"],
                subnet_emission=subnet["subnet_emission"],
                subnet_tempo=subnet["subnet_tempo"],
                num_total_validators=subnet["num_total_validators"],
                num_valid_validators=subnet["num_valid_validators"],
                rizzo_stake_rank=subnet["rizzo_stake_rank"],
                rizzo_emission=subnet["rizzo_emission"],
                rizzo_vtrust=subnet["rizzo_vtrust"],
                max_vtrust=subnet["max_vtrust"],
                avg_vtrust=subnet["avg_vtrust"],
                min_vtrust=subnet["min_vtrust"],
                rizzo_updated=subnet["rizzo_updated"],
                min_updated=subnet["min_updated"],
                avg_updated=subnet["avg_updated"],
                max_updated=subnet["max_updated"],)


class SubnetDataFromJson(SubnetDataBase):
    def __init__(self, json_file, host, port, username, ssh_key_path, password, debug):
        self._json_file = json_file
        self._host = host
        self._port = port
        self._username = username
        self._ssh_key_path = ssh_key_path
        self._password = password

        super(SubnetDataFromJson, self).__init__(debug)

    def _get_subnet_data(self):
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if self._ssh_key_path:
            ssh_key = paramiko.RSAKey.from_private_key_file(self._ssh_key_path)
            auth_arg = {"pkey": ssh_key}
        else:
            auth_arg = {"password": self._password}
        client.connect(
            self._host,
            port=self._port,
            username=self._username,
            **auth_arg)

        stdin, stdout, stderr = client.exec_command(f"cat {self._json_file}")
        json_str = stdout.read().decode()

        stdin.close()
        stdout.close()
        stderr.close()
        client.close()
        subnets_data = json.loads(json_str)
        for subnet in subnets_data.values():
            self._validator_data[subnet["netuid"]] = self.ValidatorData(
                netuid=subnet["netuid"],
                subnet_emission=subnet["subnet_emission"],
                subnet_tempo=subnet["subnet_tempo"],
                num_total_validators=subnet["num_total_validators"],
                num_valid_validators=subnet["num_valid_validators"],
                rizzo_stake_rank=subnet["rizzo_stake_rank"],
                rizzo_emission=subnet["rizzo_emission"],
                rizzo_vtrust=subnet["rizzo_vtrust"],
                max_vtrust=subnet["max_vtrust"],
                avg_vtrust=subnet["avg_vtrust"],
                min_vtrust=subnet["min_vtrust"],
                rizzo_updated=subnet["rizzo_updated"],
                min_updated=subnet["min_updated"],
                avg_updated=subnet["avg_updated"],
                max_updated=subnet["max_updated"],)
