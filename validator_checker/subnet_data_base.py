# Future imports
from __future__ import annotations

# bittensor import
import bittensor

# standart imports
from dataclasses import asdict

# Local imports
from .constants import (
    COLDKEYS,
    MULTI_UID_HOTKEYS,
    RIZZO_HOTKEYS,
)


class SubnetDataBase:
    def __init__(self):
        self._validator_data = {}

        # Gather the data for all given subnets
        self._get_subnet_data()

    @property
    def netuids(self):
        return self._netuids

    @property
    def validator_data(self):
        return self._validator_data

    @property
    def as_dict(self):
        return {
            netuid: asdict(self._validator_data[netuid])
            for netuid in self._validator_data
        }

    def _get_subnet_data(self):
        raise NotImplementedError


class SubnetDataFromSubtensor(SubnetDataBase):
    @staticmethod
    def _get_other_coldkey(other_coldkey):
        if not other_coldkey:
            return None
        for vali_name in COLDKEYS:
            if other_coldkey.lower().replace(".", "_") == vali_name.lower():
                return COLDKEYS[vali_name]
        return other_coldkey

    def _get_uid(self, metagraph):
        if self._other_coldkey:
            return self._get_other_vali_uid(metagraph, self._other_coldkey)

        # This is a fix to handle the subnets on which we're registered on
        # multiple uids.
        if metagraph.netuid in MULTI_UID_HOTKEYS:
            hotkey = RIZZO_HOTKEYS[metagraph.netuid]
            try:
                return metagraph.hotkeys.index(hotkey)
            except ValueError:
                # We're not registered
                return None

        try:
            return metagraph.coldkeys.index(COLDKEYS["Rizzo"])
        except ValueError:
            # We're not registered
            return None

    @staticmethod
    def _get_other_vali_uid(metagraph, vali_coldkey):
        num_uids = metagraph.coldkeys.count(vali_coldkey)

        # Not registered
        if num_uids == 0:
            return None

        # Registered with one uid
        if num_uids == 1:
            return metagraph.coldkeys.index(vali_coldkey)

        # Registered with multiple uids
        uids = [i for i, c in enumerate(metagraph.coldkeys) if c == vali_coldkey]
        for uid in uids:
            if metagraph.validator_permit[uid]:
                return uid
        return uids[0]  # I don't know if its best to return first uid or nothing.

    async def _async_get_subnet_data(self):
        def get_chunks():
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

        bittensor.logging.info(f"Connecting to subtensor network: {self._network}")

        async with bittensor.AsyncSubtensor(network=self._network) as subtensor:
            # If netuids arg was not passed in, get all netuids from the subtensor here.
            if not self._netuids:
                all_subnets = await subtensor.get_all_subnets_netuid()
                self._netuids = all_subnets[1:]

            # If chunk_size is 0, get chunk_size after we know that we have the list of netuids.
            if not self._chunk_size:
                self._chunk_size = len(self._netuids)

            bittensor.logging.info(f"Gathering data in chunks of {self._chunk_size}")

            max_attempts = 5
            for netuids in get_chunks():
                for attempt in range(1, max_attempts+1):
                    bittensor.logging.info(f"Attempt {attempt} of {max_attempts}")
                    await self._get_validator_data(subtensor, netuids)

                    # Get netuids missing data
                    # I don't think this is needed anymore but keeping it around
                    # just in case.
                    netuids = list(set(netuids).difference(set(self._validator_data)))
                    if netuids:
                        bittensor.logging.error(
                            "Failed to gather data for subnets: "
                            f"{', '.join([str(n) for n in netuids])}."
                        )
                    else:
                        break
