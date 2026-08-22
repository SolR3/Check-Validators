# Future imports
from __future__ import annotations

# standart imports
from dataclasses import asdict

# bittensor import
import bittensor

# Local imports
from .constants import (
    COLDKEYS,
    MULTI_UID_HOTKEYS,
    RIZZO_HOTKEYS,
)
from .utils import logger


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
            if metagraph.neurons[uid].validator_permit:
                return uid
        return uids[0]  # I don't know if its best to return first uid or nothing.

    @staticmethod
    async def _get_subnet_emissions(snapshot, netuids):
        tao_emission = await snapshot.query_map(
            bittensor.storage.SubtensorModule.SubnetTaoInEmission
        )
        tao_emission = dict(tao_emission)

        excess_tao = await snapshot.query_map(
            bittensor.storage.SubtensorModule.SubnetExcessTao
        )
        excess_tao = dict(excess_tao)

        raw_emission = {
            n: tao_emission.get(n, 0) + excess_tao.get(n, 0)
            for n in set(list(tao_emission) + list(excess_tao))
        }
        total_emission = sum(raw_emission.values())

        return [(raw_emission.get(n, 0.0) / total_emission * 100) for n in netuids]

    @staticmethod
    async def _get_mech_split(subtensor, netuid):
        # mechanism_emission_split will return None for subnets that have one mech
        # so replace None with a list with a single emission value of 100%
        mech_splits = await subtensor.subnets.mechanism_emission_split(netuid)
        mech_splits = (
            [round((m / bittensor.settings.U16_MAX) * 100) for m in mech_splits]
            if mech_splits else [100]
        )
        return mech_splits

    @staticmethod
    async def _get_metagraph(subtensor, netuid):
        metagraph = await subtensor.subnets.metagraph(netuid, commitments=False)
        return metagraph

    @staticmethod
    async def _get_last_update(subtensor, netuid, mechid):
        last_update_index = mechid * bittensor.settings.GLOBAL_MAX_SUBNET_COUNT + netuid
        last_update = await subtensor.query(
            bittensor.storage.SubtensorModule.LastUpdate,
            params=[last_update_index]
        )
        return last_update

    @staticmethod
    async def _get_vtrust(subtensor, netuid):
        vtrust = await subtensor.query(
            bittensor.storage.SubtensorModule.ValidatorTrust,
            params=[netuid]
        )
        return [vt / bittensor.settings.U16_MAX for vt in vtrust]

    async def _get_children(self, subtensor, netuid):
        children = await subtensor.delegation.children(self._get_chk_hotkey(), netuid)
        return [(c[0] / (2**64 - 1), c[1]) for c in children]

    async def _get_pending_children(self, subtensor, netuid):
        pending_children = await subtensor.delegation.pending_children(self._get_chk_hotkey(), netuid)
        pending_children["children"] = [(c[0] / (2**64 - 1), c[1]) for c in pending_children["children"]]
        return pending_children

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

        logger.info(f"Connecting to subtensor network: {self._network}")

        async with bittensor.Subtensor(network=self._network) as subtensor:
            # Get the current block.
            block = await subtensor.block()

            # If netuids arg was not passed in, get all netuids from the subtensor here.
            if not self._netuids:
                subnets = await subtensor.subnets.all(block=block)
                self._netuids = [sn.netuid for sn in subnets][1:]

            # If chunk_size is 0, get chunk_size after we know that we have the list of netuids.
            if not self._chunk_size:
                self._chunk_size = len(self._netuids)

            logger.info(f"Gathering data in chunks of {self._chunk_size}")

            max_attempts = 5
            for netuids in get_chunks():
                for attempt in range(1, max_attempts+1):
                    logger.info(f"Attempt {attempt} of {max_attempts}")
                    await self._get_validator_data(subtensor, block, netuids)

                    # Get netuids missing data
                    # I don't think this is needed anymore but keeping it around
                    # just in case.
                    netuids = list(set(netuids).difference(set(self._validator_data)))
                    if netuids:
                        logger.error(
                            "Failed to gather data for subnets: "
                            f"{', '.join([str(n) for n in netuids])}."
                        )
                    else:
                        break

    async def _get_validator_data(self, *args, **kwargs):
        raise NotImplementedError
