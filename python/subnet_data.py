# bittensor import
from bittensor.core.async_subtensor import AsyncSubtensor
from bittensor.utils import u16_normalized_float

# standart imports
import asyncio
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
# import json
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
        "rt21_vtrust",
        "rt21_vtrust_gap",
        "max_vtrust",
        "avg_vtrust",
        "min_vtrust",
        "rizzo_updated",
        "min_updated",
        "avg_updated",
        "max_updated",
        "chk_fraction",
        "chk_vtrust",
        "chk_updated",
        "chk_pending_block",
        "chk_pending_time",
        "child_hotkey_data",
        "pending_child_hotkey_data",
        "validator_hotkeys",
        ]
    )
    ChildHotkeyData = namedtuple(
        "ChildHotkeyData", [
            "fraction",
            "hotkey",
            "take",
            "vtrust",
            "updated",
        ]
    )
    ValidatorHotkeys = namedtuple(
        "ValidatorHotkeys", [
            "Rizzo",
            "Rt21",
            "OTF",
            "Yuma",
        ]
    )

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
    _rizzo_chk_hotkey = "5GduQSUxNJ4E3ReCDoPDtoHHgeoE4yHmnnLpUXBz9DAwmHWV"
    _coldkeys = {
        "Rizzo": "5CMEwRYLefRmtJg7zzRyJtcXrQqmspr9B1r1nKySDReA37Z1",
        "Rt21": "5GZSAgaVGQqegjhEkxpJjpSVLVmNnE2vx2PFLzr7kBBMKpGQ",
        "OTF": "5HBtpwxuGNL1gwzwomwR7sjwUt8WXYSuWcLYN6f9KpTZkP4k",
        "Yuma": "5E9fVY1jexCNVMjd2rdBsAxeamFGEMfzHcyTn2fHgdHeYc5p",
    }

    def __init__(
            self, netuids, network, threads, debug,
            other_coldkey=None, other_chk_hotkey=None
        ):
        self._netuids = netuids
        self._network = network
        self._threads = threads
        self._other_coldkey = other_coldkey
        self._other_chk_hotkey = other_chk_hotkey

        self._validator_data_lock = threading.Lock()

        super(SubnetData, self).__init__(debug)

    def to_dict(self):
        def serializable(value):
            if (
                isinstance(value, self.ChildHotkeyData)
                or isinstance(value, self.ValidatorHotkeys)
            ):
                return namedtuple_to_dict(value)
            if isinstance(value, list):
                return [serializable(v) for v in value]
            if isinstance(value, numpy.float32):
                return float(value)
            if isinstance(value, numpy.int64):
                return int(value)
            return value

        def namedtuple_to_dict(data):
            return dict(
                [(f, serializable(getattr(data, f))) for f in data._fields]
            )

        data_dict = {}
        for netuid in self._validator_data:
            data = self._validator_data[netuid]
            data_dict[netuid] = dict(
                [(f, serializable(getattr(data, f))) for f in data._fields])
        return data_dict

    def _get_uid(self, metagraph):
        coldkey = self._other_coldkey or self._coldkeys["Rizzo"]
        try:
            return metagraph.coldkeys.index(coldkey)
        except ValueError:
            return None

    def _get_chk_hotkey(self):
        return self._other_chk_hotkey or self._rizzo_chk_hotkey

    def _get_subnet_data(self):
        self._print_debug("\nGathering data")

        max_attempts = 5
        netuids = self._netuids
        for attempt in range(1, max_attempts+1):
            self._print_debug(f"\nAttempt {attempt} of {max_attempts}")
            if self._threads:
                # TODO - This could be way better now that it's using asyncio.
                #        Or just get rid of threading now.
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

        async with AsyncSubtensor(network=self._network) as subtensor:
            # Get the block to pass to async calls so everything is in sync
            block = await subtensor.block

            # No point in printing CHK column when checking a different
            # coldkey until we figure out exactly how the CHK'ing is going
            # to work for us vs. rt21 and others and the code is updated
            # accordingly.
            if self._other_coldkey:
                children = [(True, [], '') for _ in netuids]
                children_pending = [([], 0) for _ in netuids]
            else:
                # Get the list of child hotkeys for each netuid
                children = await asyncio.gather(
                    *[
                        subtensor.get_children(netuid=netuid, hotkey=self._get_chk_hotkey())
                        for netuid in netuids
                    ]
                )

                # Get the list of pending child hotkeys for each netuid
                children_pending = await asyncio.gather(
                    *[
                        subtensor.get_children_pending(netuid=netuid, hotkey=self._get_chk_hotkey())
                        for netuid in netuids
                    ]
                )

            # Get the metagraph for each netuid
            metagraphs = await asyncio.gather(
                *[
                    subtensor.metagraph(netuid=netuid, block=block)
                    for netuid in netuids
                ]
            )

            # Get the take for each child hotkey on each netuid.
            chk_takes_dict = await self._get_child_hotkey_take_data(
                subtensor, netuids, children, False
            )

            # Get the take for each pending child hotkey on each netuid.
            chk_takes_pending_dict = await self._get_child_hotkey_take_data(
                subtensor, netuids, children_pending, True
            )

            # Get all of the rest of the data from the metagraph.
            for i, netuid in enumerate(netuids):
                metagraph = metagraphs[i]
                child_hotkeys = children[i][1]
                child_takes = chk_takes_dict.get(netuid, [])
                child_hotkeys_pending, chk_pending_block = children_pending[i]
                child_takes_pending = chk_takes_pending_dict.get(netuid, [])
                self._get_data_from_metagraph(
                    metagraph, netuid, child_hotkeys, child_takes,
                    child_hotkeys_pending, child_takes_pending,
                    block, chk_pending_block
                )

        total_time = time.time() - start_time
        self._print_debug(f"\nData gathered in {int(total_time)} seconds "
                          f"for subnets: {netuids}.")

    async def _get_child_hotkey_take_data(
            self, subtensor, netuids, children, do_pending
    ):
        # Get the take for each child hotkey on each netuid.
        chk_take_func_calls = []
        chk_take_funcs_dict = {}
        chk_takes_dict = {}
        func_call_index = 0
        for i, netuid in enumerate(netuids):
            if do_pending:
                child_hotkeys, _ = children[i]
            else:
                success, child_hotkeys, msg = children[i]
                if not success:
                    self._print_debug(
                        f"Failed to obtain child hotkeys from netuid {netuid}: {msg}"
                    )

            chk_take_funcs_dict[netuid] = []
            for _, child_hotkey in child_hotkeys:
                chk_take_func_calls.append(
                    subtensor.substrate.query(
                        module="SubtensorModule",
                        storage_function="ChildkeyTake",
                        params=[child_hotkey, netuid]
                    )
                )
                chk_take_funcs_dict[netuid].append(func_call_index)
                func_call_index += 1
        all_child_takes = (
            [u16_normalized_float(r.value) for r in await asyncio.gather(*chk_take_func_calls)]
            if chk_take_func_calls else []
        )

        # Massage the child take data to make it easier to obtain later on.
        for i, netuid in enumerate(netuids):
            cti = chk_take_funcs_dict.get(netuid)
            chk_takes_dict[netuid] = all_child_takes[cti[0]:cti[-1]+1] if cti else []

        return chk_takes_dict

    def _get_data_from_metagraph(
            self, metagraph, netuid, child_hotkeys, child_takes,
            child_hotkeys_pending, child_takes_pending,
            current_block, chk_pending_block
    ):
        # Get the hotkeys that we care about (Rizzo, Rt21, etc.)
        vali_hotkeys = {}
        for vali_name, vali_coldkey in self._coldkeys.items():
            try:
                vali_index = metagraph.coldkeys.index(vali_coldkey)
            except ValueError:
                vali_hotkeys[vali_name] = None
            else:
                vali_hotkeys[vali_name] = metagraph.hotkeys[vali_index]
        validator_hotkeys = self.ValidatorHotkeys(**vali_hotkeys)

        # Get emission percentage for the subnet.
        subnet_emission = metagraph.emissions.tao_in_emission * 100

        # Get subnet tempo (used for determining bad Updated values)
        # subnet_tempo = subtensor.get_subnet_hyperparameters(netuid).tempo
        subnet_tempo = 360

        # Get Rizzo validator data
        rizzo_uid = self._get_uid(metagraph)
        if rizzo_uid is None:
            self._print_debug(
                "\nWARNING: Rizzo validator not running on subnet "
                f"{netuid}"
            )
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

        # Get child hotkey data
        chk_fraction = 0.0
        child_hotkey_data = []
        if len(child_hotkeys) == 0:
            chk_vtrust = None
            chk_updated = None
        else:
            chk_vtrust = 0.0
            chk_updated = 0
            for i, (child_fraction, child_hotkey) in enumerate(child_hotkeys):
                child_take = child_takes[i]
                try:
                    child_uid = metagraph.hotkeys.index(child_hotkey)
                except ValueError:
                    child_vtrust = None
                    child_updated = None
                else:
                    child_vtrust = metagraph.Tv[child_uid]
                    child_updated = current_block - metagraph.last_update[child_uid]

                child_hotkey_data.append(
                    self.ChildHotkeyData(
                        fraction=child_fraction,
                        hotkey=child_hotkey,
                        take=child_take,
                        vtrust=child_vtrust,
                        updated=child_updated,
                    )
                )

                # Calculate total chk stats
                chk_fraction += child_fraction
                chk_vtrust += (child_vtrust or 0.0) * child_fraction
                if child_updated is not None and child_updated > chk_updated:
                    chk_updated = child_updated

            chk_vtrust /= chk_fraction

        # Get pending child hotkey data
        pending_child_hotkey_data = []
        if chk_pending_block == 0:
            chk_pending_block = None
            chk_pending_time = None
        else:
            chk_pending_time = (chk_pending_block - current_block) * 12
            for i, (child_fraction, child_hotkey) in enumerate(child_hotkeys_pending):
                child_take = child_takes_pending[i]
                try:
                    child_uid = metagraph.hotkeys.index(child_hotkey)
                except ValueError:
                    child_vtrust = None
                    child_updated = None
                else:
                    child_vtrust = metagraph.Tv[child_uid]
                    child_updated = current_block - metagraph.last_update[child_uid]

                pending_child_hotkey_data.append(
                    self.ChildHotkeyData(
                        fraction=child_fraction,
                        hotkey=child_hotkey,
                        take=child_take,
                        vtrust=child_vtrust,
                        updated=child_updated,
                    )
                )

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

        # Get rt21 vTrust
        try:
            rt21_uid = metagraph.coldkeys.index(self._coldkeys["Rt21"])
        except ValueError:
            rt21_vtrust = None
        else:
            rt21_vtrust = metagraph.Tv[rt21_uid]
        rt21_vtrust_gap = (
            rt21_vtrust - rizzo_vtrust
            if rt21_vtrust is not None and rizzo_vtrust is not None
            else None
        )

        # Get other validator data
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
                rt21_vtrust=rt21_vtrust,
                rt21_vtrust_gap=rt21_vtrust_gap,
                max_vtrust=max_vtrust,
                avg_vtrust=avg_vtrust,
                min_vtrust=min_vtrust,
                rizzo_updated=rizzo_updated,
                min_updated=min_updated,
                avg_updated=avg_updated,
                max_updated=max_updated,
                chk_fraction=chk_fraction,
                chk_vtrust=chk_vtrust,
                chk_updated=chk_updated,
                chk_pending_block=chk_pending_block,
                chk_pending_time=chk_pending_time,
                child_hotkey_data=child_hotkey_data,
                pending_child_hotkey_data=pending_child_hotkey_data,
                validator_hotkeys=validator_hotkeys,
            )


# class SubnetDataFromWebServer(SubnetDataBase):
#     def __init__(self, public_ip, port, username, password, debug):
#         self._public_ip = public_ip
#         self._port = port
#         self._username = username
#         self._password = password

#         super(SubnetDataFromWebServer, self).__init__(debug)

#     def _get_subnet_data(self):
#         from bs4 import BeautifulSoup
#         import requests

#         subnets_data = {}

#         main_url = f"http://{self._public_ip}:{self._port}"
#         self._print_debug(f"Obtaining validator json data from: {main_url}")
#         response = requests.get(main_url, auth=(self._username, self._password))
#         if response.status_code != 200:
#             self._print_debug("\nERROR: Failed to obtain validator json data."
#                               f"\nurl: {main_url}"
#                               f"\nstatus code: {response.status_code}"
#                               f"\nreason: {response.reason}")
#             return

#         html_content = BeautifulSoup(response.content.decode(), features="html.parser")
#         for li_tag in html_content.findAll("li"):
#             json_file = li_tag.find("a").get("href")
#             json_url = f"http://{self._public_ip}:{self._port}/{json_file}"
#             self._print_debug(f"Updating validator json data with: {json_url}")
#             response = requests.get(json_url, auth=(self._username, self._password))
#             if response.status_code != 200:
#                 self._print_debug("\nERROR: Failed to obtain validator json data."
#                                   f"\nurl: {json_url}"
#                                   f"\nstatus code: {response.status_code}"
#                                   f"\nreason: {response.reason}")
#                 return
            
#             subnets_data.update(response.json())

#         for subnet in subnets_data.values():
#             self._validator_data[subnet["netuid"]] = self.ValidatorData(
#                 netuid=subnet["netuid"],
#                 subnet_emission=subnet["subnet_emission"],
#                 subnet_tempo=subnet["subnet_tempo"],
#                 num_total_validators=subnet["num_total_validators"],
#                 num_valid_validators=subnet["num_valid_validators"],
#                 rizzo_stake_rank=subnet["rizzo_stake_rank"],
#                 rizzo_emission=subnet["rizzo_emission"],
#                 rizzo_vtrust=subnet["rizzo_vtrust"],
#                 max_vtrust=subnet["max_vtrust"],
#                 avg_vtrust=subnet["avg_vtrust"],
#                 min_vtrust=subnet["min_vtrust"],
#                 rizzo_updated=subnet["rizzo_updated"],
#                 min_updated=subnet["min_updated"],
#                 avg_updated=subnet["avg_updated"],
#                 max_updated=subnet["max_updated"],
#                 chk_fraction=subnet["chk_fraction"],
#                 chk_vtrust=subnet["chk_vtrust"],
#                 chk_updated=subnet["chk_updated"],
#                 child_hotkey_data=subnet["child_hotkey_data"])


# class SubnetDataFromJson(SubnetDataBase):
#     def __init__(self, json_file, host, port, username, ssh_key_path, password, debug):
#         self._json_file = json_file
#         self._host = host
#         self._port = port
#         self._username = username
#         self._ssh_key_path = ssh_key_path
#         self._password = password

#         super(SubnetDataFromJson, self).__init__(debug)

#     def _get_subnet_data(self):
#         import paramiko

#         client = paramiko.SSHClient()
#         client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

#         if self._ssh_key_path:
#             ssh_key = paramiko.RSAKey.from_private_key_file(self._ssh_key_path)
#             auth_arg = {"pkey": ssh_key}
#         else:
#             auth_arg = {"password": self._password}
#         client.connect(
#             self._host,
#             port=self._port,
#             username=self._username,
#             **auth_arg)

#         stdin, stdout, stderr = client.exec_command(f"cat {self._json_file}")
#         json_str = stdout.read().decode()

#         stdin.close()
#         stdout.close()
#         stderr.close()
#         client.close()
#         subnets_data = json.loads(json_str)
#         for subnet in subnets_data.values():
#             self._validator_data[subnet["netuid"]] = self.ValidatorData(
#                 netuid=subnet["netuid"],
#                 subnet_emission=subnet["subnet_emission"],
#                 subnet_tempo=subnet["subnet_tempo"],
#                 num_total_validators=subnet["num_total_validators"],
#                 num_valid_validators=subnet["num_valid_validators"],
#                 rizzo_stake_rank=subnet["rizzo_stake_rank"],
#                 rizzo_emission=subnet["rizzo_emission"],
#                 rizzo_vtrust=subnet["rizzo_vtrust"],
#                 max_vtrust=subnet["max_vtrust"],
#                 avg_vtrust=subnet["avg_vtrust"],
#                 min_vtrust=subnet["min_vtrust"],
#                 rizzo_updated=subnet["rizzo_updated"],
#                 min_updated=subnet["min_updated"],
#                 avg_updated=subnet["avg_updated"],
#                 max_updated=subnet["max_updated"],
#                 chk_fraction=subnet["chk_fraction"],
#                 chk_vtrust=subnet["chk_vtrust"],
#                 chk_updated=subnet["chk_updated"],
#                 child_hotkey_data=subnet["child_hotkey_data"])
