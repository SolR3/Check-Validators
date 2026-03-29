# Future imports
from __future__ import annotations

# bittensor import
import bittensor

# standart imports
import asyncio
from dataclasses import dataclass, asdict
import json
import numpy
import os
import re
import time

# Local imports
from constants import (
    MIN_VTRUST_THRESHOLD,
    MAX_U_THRESHOLD,
    COLDKEYS,
    MULTI_UID_HOTKEYS,
    RIZZO_HOTKEYS,
    DATA_FILE_NAME,
)
import utils


class SubnetDataBase:
    @dataclass
    class ValidatorData:
        subnet_emission: float
        blocks: list[int]
        block_data: list[SubnetDataBase.BlockData]

    @dataclass
    class BlockData:
        rizzo_emission: float
        rizzo_vtrust: float
        avg_vtrust: float | None
        rizzo_updated: int | None

    def __init__(self):
        self._validator_data = {}

        # Gather the data for all given subnets
        self._get_subnet_data()

    @property
    def validator_data(self):
        return self._validator_data

    def as_dict(self):
        return {
            netuid: asdict(self._validator_data[netuid])
            for netuid in self._validator_data
        }

    def _get_subnet_data(self):
        raise NotImplementedError


class SubnetDataIntervals(SubnetDataBase):
    def __init__(
            self, netuids, num_intervals, network, chunk_size=0,
            other_coldkey=None, existing_data=None
    ):
        self._netuids = netuids
        self._network = network
        self._chunk_size = chunk_size or len(self._netuids)
        self._num_intervals = num_intervals
        self._other_coldkey = self._get_other_coldkey(other_coldkey)
        self._existing_data = existing_data or {}

        super().__init__()

    @staticmethod
    def _get_other_coldkey(other_coldkey):
        if not other_coldkey:
            return None
        for vali_name in COLDKEYS:
            if other_coldkey.lower().replace(".", "_") == vali_name.lower():
                return COLDKEYS[vali_name]
        return other_coldkey

    def _get_subnet_data(self):
        asyncio.run(self._async_get_subnet_data())

    async def _async_get_subnet_data(self):
        bittensor.logging.info(f"Gathering data in chunks of {self._chunk_size}")

        bittensor.logging.info(f"Connecting to subtensor network: {self._network}")
        async with bittensor.AsyncSubtensor(network=self._network) as subtensor:
            max_attempts = 5
            for netuids in self._get_chunks():
                for attempt in range(1, max_attempts+1):
                    bittensor.logging.info(f"Attempt {attempt} of {max_attempts}")
                    await self._get_validator_data(subtensor, netuids)

                    # Get netuids missing data
                    netuids = list(set(netuids).difference(set(self._validator_data)))
                    if netuids:
                        bittensor.logging.error(
                            "Failed to gather data for subnets: "
                            f"{', '.join([str(n) for n in netuids])}."
                        )
                    else:
                        break

    def _get_chunks(self):
        num_netuids = len(self._netuids)
        netuid_start = 0
        while True:
            netuid_end = netuid_start + self._chunk_size
            if netuid_end >= num_netuids:
                yield self._netuids[netuid_start:]
                break
            else:
                yield self._netuids[netuid_start:netuid_end]
                netuid_start = netuid_end

    async def _get_validator_data(self, subtensor, all_netuids):
        start_time = time.time()
        bittensor.logging.info(f"Obtaining data for subnets: {all_netuids}")

        # Get the block to pass to async calls so everything is in sync
        block = await subtensor.block

        # Get the metagraphs.
        metagraphs = await asyncio.gather(
            *[
                subtensor.metagraph(netuid=netuid, block=block)
                for netuid in all_netuids
            ]
        )

        block_to_stop = {}
        last_weight_set_block = {}
        for ni, netuid in enumerate(all_netuids):
            metagraph = metagraphs[ni]
            # Get emission percentages.
            # Multiplying by 2 since tao has been halved?
            subnet_emission = metagraph.emissions.tao_in_emission * 100 * 2

            self._validator_data[netuid] = self.ValidatorData(
                subnet_emission=subnet_emission,
                blocks=[],
                block_data=[],
            )

            # Get UID for Rizzo.
            try:
                rizzo_uid = self._get_rizzo_uid(metagraph)
            except ValueError:
                bittensor.logging.warning(
                    f"Rizzo validator not running on subnet {netuid}"
                )
                continue

            last_weight_set_block[netuid] = int(metagraph.last_update[rizzo_uid])

            if self._existing_data.get(netuid):
                block_to_stop[netuid] = (
                    self._existing_data[netuid].blocks[0]
                        if self._existing_data[netuid].blocks
                    else 0  # last_weight_set_block[netuid] - 1
                )
            else:
                block_to_stop[netuid] = 0

        netuids = all_netuids[:]
        for _ in range(self._num_intervals):
            netuids = [
                n for n in netuids
                if n in block_to_stop
                and last_weight_set_block[n] > block_to_stop[n]
            ]

            if not netuids:
                break

            #
            # For some reason this raises random errors:
            #     "Failed to decode type: "scale_info::580" with type id: 580"
            # and it seems non-deterministic.
            # Putting this in a loop.
            #
            metagraphs = {}
            netuids_remaining = netuids[:]
            max_attemps = 3
            for attempt in range(max_attemps):
                bittensor.logging.info(f"Attempt {attempt+1}: {netuids_remaining}")
                mgs = await asyncio.gather(
                    *[
                        self.get_metagraph_for_netuid_at_block(
                            subtensor, netuid, last_weight_set_block[netuid] - 1
                        )
                        for netuid in netuids_remaining
                    ]
                )
                failed_netuids = []
                for ni, netuid in enumerate(netuids_remaining):
                    if mgs[ni]:
                        metagraphs[netuid] = mgs[ni]
                    else:
                        failed_netuids.append(netuid)
                if not failed_netuids:
                    break
                netuids_remaining = failed_netuids

            for netuid in netuids:
                if netuid not in metagraphs:
                    bittensor.logging.warning(
                        f"Unable to obtain all {self._num_intervals} "
                        f"weight setting intervals for subnet {netuid}."
                    )
                    del block_to_stop[netuid]
                    continue

                metagraph = metagraphs[netuid]
                if not metagraph:
                    bittensor.logging.warning(
                        f"Unable to obtain all {self._num_intervals} "
                        f"weight setting intervals for subnet {netuid}."
                    )
                    del block_to_stop[netuid]
                    continue

                # Get UID for Rizzo.
                try:
                    rizzo_uid = self._get_rizzo_uid(metagraph)
                except ValueError:
                    bittensor.logging.warning(
                        f"Unable to obtain all {self._num_intervals} "
                        f"weight setting intervals for subnet {netuid}."
                    )
                    del block_to_stop[netuid]
                    continue

                # There's some weirdness going on with sn72. Catching it here.
                try:
                    prev_weight_set_block = int(metagraph.last_update[rizzo_uid])
                    interval = last_weight_set_block[netuid] - prev_weight_set_block
                    rizzo_vtrust = float(metagraph.Tv[rizzo_uid])
                    rizzo_emission = float(metagraph.E[rizzo_uid])

                    # Get all validator uids that have validator permits.
                    all_uids = metagraph.uids[
                        metagraph.validator_permit & (metagraph.uids != rizzo_uid)
                    ]
                    # Get all validators that have proper VT and U
                    valid_uids = [
                        i for i in all_uids
                        if (metagraph.Tv[i] > MIN_VTRUST_THRESHOLD)
                        & (
                            last_weight_set_block[netuid] - metagraph.last_update[i]
                            < MAX_U_THRESHOLD
                        )
                    ]

                    if not valid_uids:
                        avg_vtrust = None
                    else:
                        # Get min/max/average vTrust values.
                        # vtrusts = [metagraph.Tv[uid] for uid in valid_uids]
                        avg_vtrust = float(numpy.average(metagraph.Tv[valid_uids]))
                except IndexError:
                    bittensor.logging.warning(
                        f"Unable to obtain all {self._num_intervals} "
                        f"weight setting intervals for subnet {netuid}."
                    )
                    del block_to_stop[netuid]
                    continue

                block_data = self.BlockData(
                    rizzo_emission=rizzo_emission,
                    rizzo_vtrust=rizzo_vtrust,
                    avg_vtrust=avg_vtrust,
                    rizzo_updated=interval,
                )
                self._validator_data[netuid].blocks.append(last_weight_set_block[netuid])
                self._validator_data[netuid].block_data.append(block_data)

                last_weight_set_block[netuid] = prev_weight_set_block

        for netuid in all_netuids:
            if self._existing_data.get(netuid):
                self._validator_data[netuid].blocks.extend(
                    self._existing_data[netuid].blocks
                )
                self._validator_data[netuid].block_data.extend(
                    self._existing_data[netuid].block_data
                )
                if len(self._validator_data[netuid].blocks) > self._num_intervals:
                    self._validator_data[netuid].blocks = \
                        self._validator_data[netuid].blocks[:self._num_intervals]
                    self._validator_data[netuid].block_data = \
                        self._validator_data[netuid].block_data[:self._num_intervals]

        total_time = round(time.time() - start_time)
        bittensor.logging.info(
            f"Subnet data gathered in {utils.get_formatted_time(total_time)}."
        )

    def _get_rizzo_uid(self, metagraph):
        if not self._other_coldkey and metagraph.netuid in MULTI_UID_HOTKEYS:
            return metagraph.hotkeys.index(
                RIZZO_HOTKEYS[metagraph.netuid]
            )

        coldkey = self._other_coldkey or COLDKEYS["Rizzo"]
        return metagraph.coldkeys.index(coldkey)

    async def get_metagraph_for_netuid_at_block(self, subtensor, netuid, block):
        #
        # For some reason this raises random errors:
        #     "Failed to decode type: "scale_info::580" with type id: 580"
        # and it seems non-deterministic.
        # Putting this in a loop.
        #
        max_attemps = 3
        for attempt in range(max_attemps):
            try:
                return await subtensor.metagraph(
                    netuid=netuid, block=int(block)
                )
            except Exception as err:
                bittensor.logging.error(
                    f"failed attempt: {attempt+1}, netuid: {netuid}, block: {block}, error: {err}"
                )
                error = err
        bittensor.logging.error(
            f"Failed to obtain metagraph for netuid {netuid} at block {block} "
            f"after {max_attemps} attempts: {error}"
        )
        return None


class SubnetDataIntervalsFromJson(SubnetDataBase):
    def __init__(self, netuids, json_folder, num_intervals=None):
        self._netuids = netuids
        self._json_folder = json_folder
        self._num_intervals = num_intervals
        self._other_coldkey = None

        super().__init__()

    @staticmethod
    def get_json_file_name(netuid):
        json_base, json_ext = os.path.splitext(DATA_FILE_NAME)
        return f"{json_base}.{netuid}{json_ext}"

    @classmethod
    def get_netuids_from_json_folder(cls, json_folder):
        netuids = []
        json_file_pattern = cls.get_json_file_name(r"(?P<netuid>\d+)")
        json_file_pattern = json_file_pattern.replace(".", r"\.")
        json_file_regex = re.compile(rf"^{json_file_pattern}$")
        for _file in os.listdir(json_folder):
            regex_match = json_file_regex.match(_file)
            if regex_match:
                netuids.append(int(regex_match.group("netuid")))

        return sorted(netuids)

    def _get_subnet_data(self):
        for netuid in self._netuids:
            self._validator_data[netuid] = self.ValidatorData(
                subnet_emission=None,
                blocks=[],
                block_data=[],
            )

            json_file = os.path.join(
                self._json_folder, self.get_json_file_name(netuid)
            )
            if not os.path.isfile(json_file):
                bittensor.logging.info(
                    f"Json file ({json_file}) for netuid {netuid} does not exist."
                )
                continue

            bittensor.logging.info(
                f"Obtaining existing data from json file ({json_file}) "
                f"for netuid {netuid}."
            )

            with open(json_file, "r") as fd:
                subnet_data = json.load(fd)

            subnet_data = subnet_data[str(netuid)]

            block_data = []
            for subnet_block_data in subnet_data["block_data"]:
                block_data.append(
                    self.BlockData(
                        rizzo_emission=subnet_block_data["rizzo_emission"],
                        rizzo_vtrust=subnet_block_data["rizzo_vtrust"],
                        avg_vtrust=subnet_block_data["avg_vtrust"],
                        rizzo_updated=subnet_block_data["rizzo_updated"],
                    )
                )

            self._validator_data[netuid].subnet_emission = subnet_data["subnet_emission"]
            if self._num_intervals:
                self._validator_data[netuid].blocks = subnet_data["blocks"][:self._num_intervals]
                self._validator_data[netuid].block_data = block_data[:self._num_intervals]
            else:
                self._validator_data[netuid].blocks = subnet_data["blocks"]
                self._validator_data[netuid].block_data = block_data


class SubnetDataIntervalsFromMainData(SubnetDataBase):
    def __init__(
            self, netuids, validator_data_main, json_folder,
            num_intervals=None
    ):
        self._netuids = netuids
        self._validator_data_main = validator_data_main
        self._json_folder = json_folder
        self._num_intervals = num_intervals
        self._other_coldkey = None

        super().__init__()

    def _get_subnet_data(self):
        existing_intervals_data = SubnetDataIntervalsFromJson(
            self._netuids, self._json_folder
        ).validator_data

        for netuid in self._netuids:
            main_data = self._validator_data_main[netuid]
            existing_intervals = existing_intervals_data[netuid]

            self._validator_data[netuid] = self.ValidatorData(
                subnet_emission=main_data["subnet_emission"],
                blocks=[],
                block_data=[],
            )

            last_weight_block = main_data["rizzo_last_update"]
            if not last_weight_block:
                continue

            # The rizzo_emission, rizzo_vtrust, and avg_vtrust aren't 100% accurate.
            # They're actually the current values rather than the values when weights
            # were set. But the difference between those should never be more than
            # 75 blocks and usually never more than 25 blocks so it's probably
            # accurate enough.
            #
            # Interval defaults to None in case there is no existing intervals data.
            block_data = self.BlockData(
                rizzo_emission=main_data["rizzo_emission"],
                rizzo_vtrust=main_data["rizzo_vtrust"],
                avg_vtrust=main_data["avg_vtrust"],
                rizzo_updated=None,
            )

            try:
                last_written_block = existing_intervals.blocks[0]
            except IndexError:
                self._validator_data[netuid].blocks.append(last_weight_block)
                self._validator_data[netuid].block_data.append(block_data)
                continue

            # Shouldn't ever be less, but just in case...
            # No new weights were set. Just copy existing blocks and block data.
            if last_weight_block <= last_written_block:
                self._validator_data[netuid].blocks.extend(existing_intervals.blocks)
                self._validator_data[netuid].block_data.extend(existing_intervals.block_data)
                continue

            # Set the actual interval.
            interval = last_weight_block - last_written_block
            block_data.rizzo_updated = interval

            # Set the new block and block data and add the existing ones.
            self._validator_data[netuid].blocks.extend(
                [last_weight_block] + existing_intervals.blocks
            )
            self._validator_data[netuid].block_data.extend(
                [block_data] + existing_intervals.block_data
            )

            # If it's more than num_intervals then re-create it with the correct
            # number of intervals.
            if len(self._validator_data[netuid].blocks) > self._num_intervals:
                self._validator_data[netuid].blocks = \
                    self._validator_data[netuid].blocks[:self._num_intervals]
                self._validator_data[netuid].block_data = \
                    self._validator_data[netuid].block_data[:self._num_intervals]
