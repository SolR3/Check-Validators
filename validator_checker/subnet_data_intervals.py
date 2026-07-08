# Future imports
from __future__ import annotations

# bittensor import
import bittensor

# standart imports
import asyncio
from dataclasses import dataclass
import json
import numpy
import os
import re
import time

# Local imports
from .constants import (
    MIN_VTRUST_THRESHOLD,
    MAX_U_THRESHOLD,
    DATA_FILE_NAME,
)
from .subnet_data_base import SubnetDataBase, SubnetDataFromSubtensor
from .utils import (
    get_formatted_time,
    get_json_file_name,
)


class SubnetDataIntervalsBase:
    @dataclass
    class ValidatorData:
        subnet_emission: float
        subnet_alpha_price: float
        mech_block_data: list[SubnetDataIntervalsBase.MechBlockData]

    @dataclass
    class MechBlockData:
        mechid: int
        mech_emission: int
        blocks: list[int]
        block_data: list[SubnetDataIntervalsBase.BlockData]

    @dataclass
    class BlockData:
        rizzo_emission: float
        rizzo_vtrust: float
        avg_vtrust: float | None
        rizzo_updated: int | None


class SubnetDataIntervals(SubnetDataFromSubtensor, SubnetDataIntervalsBase):
    def __init__(
            self, network, num_intervals, netuids=None, chunk_size=0,
            other_coldkey=None, existing_json_data_folder=None
    ):
        self._netuids = netuids
        self._network = network
        self._chunk_size = chunk_size
        self._num_intervals = num_intervals
        self._other_coldkey = self._get_other_coldkey(other_coldkey)
        self._existing_json_data_folder = existing_json_data_folder

        super().__init__()

    def _get_subnet_data(self):
        self._get_existing_subnet_data_from_json()
        asyncio.run(self._async_get_subnet_data())

    def _get_existing_subnet_data_from_json(self):
        if self._existing_json_data_folder:
            self._existing_data = SubnetDataIntervalsFromJson(
                self._existing_json_data_folder, netuids=self._netuids
        ).validator_data
        else:
            self._existing_data = {}

    async def _get_validator_data(self, subtensor, all_netuids):
        start_time = time.time()
        bittensor.logging.info(f"Obtaining data for subnets: {all_netuids}")

        # Get the block to pass to async calls so everything is in sync
        block = await subtensor.block

        # Get the metagraphs.
        metagraphs = await asyncio.gather(
            *[
                subtensor.metagraph(netuid, block=block)
                for netuid in all_netuids
            ]
        )

        # Get mechanisms for each netuid
        mech_splits = await asyncio.gather(
            *[
                subtensor.get_mechanism_emission_split(netuid, block=block)
                for netuid in all_netuids
            ]
        )
        # get_mechanism_emission_split will return None for subnets that have one mech
        # so replace None with a list with a single emission value of 100%
        mech_splits = [m or [100] for m in mech_splits]

        mechids_data = {}
        for ni, netuid in enumerate(all_netuids):
            metagraph = metagraphs[ni]

            # Get emission percentages.
            # Multiplying by 2 since tao has been halved?
            subnet_emission = self._get_subnet_emission(metagraph)

            # Get alpha price for the subnet.
            subnet_alpha_price = self._get_subnet_alpha_price(metagraph)

            # Initialize ValidatorData for netuid.
            self._validator_data[netuid] = self.ValidatorData(
                subnet_emission=subnet_emission,
                subnet_alpha_price=subnet_alpha_price,
                mech_block_data=[],
            )

            mech_split = mech_splits[ni]
            for mechid, mech_emission in enumerate(mech_split):
                # Initialize MechBlockData for netuid.
                mech_block_data = self.MechBlockData(
                    mechid=mechid,
                    mech_emission=mech_emission,
                    blocks=[],
                    block_data=[],
                )
                self._validator_data[netuid].mech_block_data.append(mech_block_data)

                # Convert the gathered mechid splits into a nested dictionary to make it easier
                # to loop thrugh each mechid.
                mechid_data = mechids_data.setdefault(mechid, {"netuids": [], "metagraphs": []})
                mechid_data["netuids"].append(netuid)
                mechid_data["metagraphs"].append(metagraph)

        # Loop through each mechid and gather the blocks info for all netuids with that mechid.
        for mechid, mechid_data in mechids_data.items():
            netuids = mechid_data["netuids"]
            metagraphs = mechid_data["metagraphs"]
            await self._get_validator_data_for_mechid(subtensor, block, mechid, netuids, metagraphs)

        total_time = round(time.time() - start_time)
        bittensor.logging.info(
            f"Subnet data gathered in {get_formatted_time(total_time)}."
        )

    async def _get_validator_data_for_mechid(self, subtensor, block, mechid, all_netuids, metagraphs):
        if mechid:
            # If this is mech 1+ then get the last_update atts from the metagraph_infos.
            metagraph_infos = await asyncio.gather(
                *[
                    subtensor.get_metagraph_info(netuid, block=block, mechid=mechid)
                    for netuid in all_netuids
                ]
            )
            # Convert the last_update attribues in the metagraph_infos from tuples to numpy arrays.
            last_updates = [
                numpy.array(metagraph_info.last_update, dtype=int)
                for metagraph_info in metagraph_infos
            ]
        else:
            # Otherwise get the last_update atts from the metagraphs.
            last_updates = [
                metagraph.last_update for metagraph in metagraphs
            ]

        block_to_stop = {}
        last_weight_set_block = {}
        for ni, netuid in enumerate(all_netuids):
            metagraph = metagraphs[ni]

            # Get UID for Rizzo.
            rizzo_uid = self._get_uid(metagraph)
            if rizzo_uid is None:
                bittensor.logging.warning(
                    f"Rizzo validator not running on subnet {netuid}"
                )
                continue

            last_update = last_updates[ni]
            last_weight_set_block[netuid] = int(last_update[rizzo_uid])

            if (
                netuid in self._existing_data
                and mechid < len(self._existing_data[netuid].mech_block_data)
                and self._existing_data[netuid].mech_block_data[mechid].blocks
            ):
                block_to_stop[netuid] = \
                    self._existing_data[netuid].mech_block_data[mechid].blocks[0]
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
            metagraphs_data = {}
            netuids_remaining = netuids[:]
            max_attemps = 3
            for attempt in range(max_attemps):
                bittensor.logging.info(f"Attempt {attempt+1}: {netuids_remaining}")
                metagraph_data = await asyncio.gather(
                    *[
                        self._get_metagraph_data_for_netuid_at_block(
                            subtensor, netuid, mechid, last_weight_set_block[netuid] - 1
                        )
                        for netuid in netuids_remaining
                    ]
                )
                failed_netuids = []
                for ni, netuid in enumerate(netuids_remaining):
                    if metagraph_data[ni]:
                        metagraphs_data[netuid] = metagraph_data[ni]
                    else:
                        failed_netuids.append(netuid)
                if not failed_netuids:
                    break
                netuids_remaining = failed_netuids

            for netuid in netuids:
                if netuid not in metagraphs_data:
                    bittensor.logging.warning(
                        f"Unable to obtain all {self._num_intervals} "
                        f"weight setting intervals for subnet {netuid}."
                    )
                    del block_to_stop[netuid]
                    continue

                metagraph_data = metagraphs_data[netuid]
                if not metagraph_data:
                    bittensor.logging.warning(
                        f"Unable to obtain all {self._num_intervals} "
                        f"weight setting intervals for subnet {netuid}."
                    )
                    del block_to_stop[netuid]
                    continue

                metagraph, metagraph_info = metagraph_data

                # Get UID for Rizzo.
                rizzo_uid = self._get_uid(metagraph)
                if rizzo_uid is None:
                    bittensor.logging.warning(
                        f"Unable to obtain all {self._num_intervals} "
                        f"weight setting intervals for subnet {netuid}."
                    )
                    del block_to_stop[netuid]
                    continue

                # Convert the last_update attribue in the metagraph_info from a tuple to a numpy array.
                last_update = (
                    numpy.array(metagraph_info.last_update, dtype=int) if mechid
                    else metagraph.last_update
                )

                # There's some weirdness going on with sn72. Catching it here.
                try:
                    prev_weight_set_block = int(last_update[rizzo_uid])
                    interval = last_weight_set_block[netuid] - prev_weight_set_block
                    rizzo_vtrust = float(metagraph.Tv[rizzo_uid])
                    rizzo_emission = float(metagraph.E[rizzo_uid])

                    # Get all validator uids that have validator permits.
                    all_uids = metagraph.uids[
                        metagraph.validator_permit & (metagraph.uids != rizzo_uid)
                    ]
                    # Get all validators that have proper VT and U
                    valid_uids = all_uids[
                        (metagraph.Tv[all_uids] > MIN_VTRUST_THRESHOLD)
                        & (last_weight_set_block[netuid] - last_update[all_uids] < MAX_U_THRESHOLD)
                    ]

                    if not len(valid_uids):
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

                mech_block_data = self._validator_data[netuid].mech_block_data[mechid]
                mech_block_data.blocks.append(last_weight_set_block[netuid])
                mech_block_data.block_data.append(block_data)

                last_weight_set_block[netuid] = prev_weight_set_block

        for netuid in all_netuids:
            if (
                netuid in self._existing_data
                and mechid < len(self._existing_data[netuid].mech_block_data)
            ):
                mech_block_data = self._validator_data[netuid].mech_block_data[mechid]
                existing_mech_block_data = self._existing_data[netuid].mech_block_data[mechid]

                mech_block_data.blocks.extend(existing_mech_block_data.blocks)
                mech_block_data.block_data.extend(existing_mech_block_data.block_data)

                if len(mech_block_data.blocks) > self._num_intervals:
                    mech_block_data.blocks = mech_block_data.blocks[:self._num_intervals]
                    mech_block_data.block_data = mech_block_data.block_data[:self._num_intervals]

    async def _get_metagraph_data_for_netuid_at_block(self, subtensor, netuid, mechid, block):
        #
        # For some reason this raises random errors:
        #     "Failed to decode type: "scale_info::580" with type id: 580"
        # and it seems non-deterministic.
        # Putting this in a loop.
        #
        max_attemps = 3
        for attempt in range(max_attemps):
            try:
                metagraph = await subtensor.metagraph(
                    netuid, block=int(block)
                )
                if mechid:
                    metagraph_info = await subtensor.get_metagraph_info(
                        netuid, block=int(block), mechid=mechid
                    )
                else:
                    metagraph_info = None
                return metagraph, metagraph_info
            except Exception as err:
                bittensor.logging.error(
                    f"failed attempt: {attempt+1}, netuid: {netuid}, block: {block}, error: {err}"
                )

        bittensor.logging.error(
            f"Failed to obtain metagraph for netuid {netuid} at block {block} "
            f"after {max_attemps} attempts."
        )
        return None


class SubnetDataIntervalsFromJson(SubnetDataBase, SubnetDataIntervalsBase):
    def __init__(self, json_folder, netuids=None, num_intervals=None):
        self._json_folder = json_folder
        self._netuids = netuids or self._get_netuids_from_json_folder()
        self._num_intervals = num_intervals
        self._other_coldkey = None

        super().__init__()

    def _get_netuids_from_json_folder(self):
        netuids = []
        json_file_pattern = get_json_file_name(DATA_FILE_NAME, r"(?P<netuid>\d+)")
        json_file_pattern = json_file_pattern.replace(".", r"\.")
        json_file_regex = re.compile(rf"^{json_file_pattern}$")
        for _file in os.listdir(self._json_folder):
            regex_match = json_file_regex.match(_file)
            if regex_match:
                netuids.append(int(regex_match.group("netuid")))

        return sorted(netuids)

    def _get_subnet_data(self):
        for netuid in self._netuids:
            self._validator_data[netuid] = self.ValidatorData(
                subnet_emission=None,
                subnet_alpha_price=None,
                mech_block_data=[],
            )

            json_file = os.path.join(
                self._json_folder, get_json_file_name(DATA_FILE_NAME, netuid)
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
                json_data = json.load(fd)

            json_data = json_data[str(netuid)]

            self._validator_data[netuid].subnet_emission = json_data["subnet_emission"]
            self._validator_data[netuid].subnet_alpha_price = json_data["subnet_alpha_price"]

            for json_mech_block_data in json_data["mech_block_data"]:
                mech_block_data = self.MechBlockData(
                    mechid=json_mech_block_data["mechid"],
                    mech_emission=json_mech_block_data["mech_emission"],
                    blocks=[],
                    block_data=[],
                )
                self._validator_data[netuid].mech_block_data.append(mech_block_data)

                block_data = []
                for json_block_data in json_mech_block_data["block_data"]:
                    block_data.append(
                        self.BlockData(
                            rizzo_emission=json_block_data["rizzo_emission"],
                            rizzo_vtrust=json_block_data["rizzo_vtrust"],
                            avg_vtrust=json_block_data["avg_vtrust"],
                            rizzo_updated=json_block_data["rizzo_updated"],
                        )
                    )

                if self._num_intervals:
                    mech_block_data.blocks = json_mech_block_data["blocks"][:self._num_intervals]
                    mech_block_data.block_data = block_data[:self._num_intervals]
                else:
                    mech_block_data.blocks = json_mech_block_data["blocks"]
                    mech_block_data.block_data = block_data


class SubnetDataIntervalsFromMainData(SubnetDataBase, SubnetDataIntervalsBase):
    def __init__(
            self, netuids, validator_data_main, json_intervals_folder,
            num_intervals=None
    ):
        self._netuids = netuids
        self._validator_data_main = validator_data_main
        self._json_intervals_folder = json_intervals_folder
        self._num_intervals = num_intervals
        self._other_coldkey = None

        super().__init__()

    def _get_subnet_data(self):
        existing_intervals_data = SubnetDataIntervalsFromJson(
            self._json_intervals_folder, netuids=self._netuids
        ).validator_data

        for netuid in self._netuids:
            main_data = self._validator_data_main[netuid]
            existing_intervals = existing_intervals_data[netuid]

            self._validator_data[netuid] = self.ValidatorData(
                subnet_emission=main_data["subnet_emission"],
                subnet_alpha_price=main_data["subnet_alpha_price"],
                mech_block_data=[],
            )

            for mechid, mech_emission in enumerate(main_data["subnet_mechs"]):

                mech_block_data = self.MechBlockData(
                    mechid=mechid,
                    mech_emission=mech_emission,
                    blocks=[],
                    block_data=[],
                )
                self._validator_data[netuid].mech_block_data.append(mech_block_data)

                if main_data["rizzo_last_update"] is None:
                    continue

                last_weight_block = main_data["rizzo_last_update"][mechid]

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
                    existing_mech_block_data = existing_intervals.mech_block_data[mechid]
                    last_written_block = existing_mech_block_data.blocks[0]
                except IndexError:
                    mech_block_data.blocks.append(last_weight_block)
                    mech_block_data.block_data.append(block_data)
                    continue

                # Shouldn't ever be less, but just in case...
                # No new weights were set. Just copy existing blocks and block data.
                if last_weight_block <= last_written_block:
                    mech_block_data.blocks.extend(existing_mech_block_data.blocks)
                    mech_block_data.block_data.extend(existing_mech_block_data.block_data)
                    continue

                # Set the actual interval.
                interval = last_weight_block - last_written_block
                block_data.rizzo_updated = interval

                # Set the new block and block data and add the existing ones.
                mech_block_data.blocks.extend(
                    [last_weight_block] + existing_mech_block_data.blocks
                )
                mech_block_data.block_data.extend(
                    [block_data] + existing_mech_block_data.block_data
                )

                # If it's more than num_intervals then re-create it with the correct
                # number of intervals.
                if len(mech_block_data.blocks) > self._num_intervals:
                    mech_block_data.blocks = mech_block_data.blocks[:self._num_intervals]
                    mech_block_data.block_data = mech_block_data.block_data[:self._num_intervals]
