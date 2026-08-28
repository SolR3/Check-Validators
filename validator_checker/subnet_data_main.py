# Future imports
from __future__ import annotations

# standart imports
import asyncio
from dataclasses import dataclass, make_dataclass
import numpy
import time

# bittensor import
import bittensor

# Local imports
from .constants import (
    MIN_VTRUST_THRESHOLD,
    MAX_U_THRESHOLD,
    COLDKEYS,
    RIZZO_CHK_HOTKEY,
    RIZZO_HOTKEYS,
)
from .subnet_data_base import SubnetDataFromSubtensor
from .utils import logger


class SubnetDataMain(SubnetDataFromSubtensor):
    @dataclass
    class ValidatorData:
        block: int
        netuid: int
        subnet_emission: float
        subnet_alpha_price: float
        subnet_tao_pool: int
        subnet_mechs: list[int]
        subnet_tempo: int
        num_total_validators: int
        num_valid_validators: int
        rizzo_last_update: list[int] | None
        rizzo_vtrust: float | None
        rt21_vtrust: float | None
        rt21_vtrust_gap: float | None
        taocom_vtrust: float | None
        taocom_vtrust_gap: float | None
        yuma_vtrust: float | None
        yuma_vtrust_gap: float | None
        max_vtrust: float | None
        avg_vtrust: float | None
        min_vtrust: float | None
        rizzo_updated: list[int] | None
        min_updated: list[int] | None
        avg_updated: list[int] | None
        max_updated: list[int] | None
        chk_fraction: float
        chk_vtrust: float | None
        chk_updated: list[int] | None
        missing_chk: float
        chk_pending_block: int | None
        chk_pending_time: int | None
        child_hotkey_data: list[SubnetDataMain.ChildHotkeyData]
        pending_child_hotkey_data: list[SubnetDataMain.ChildHotkeyData]
        validator_hotkeys: SubnetDataMain.ValidatorHotkeys
        rizzo_expected_hotkey: str | None
        rizzo_hotkey_chk_take: float

    @dataclass
    class ChildHotkeyData:
        fraction: float
        hotkey: str
        take: float
        vtrust: float
        updated: list[int]

    ValidatorHotkeys = make_dataclass(
        "ValidatorHotkeys", [(k, str) for k in COLDKEYS]
    )

    def __init__(self, network, netuids=None, chunk_size=0, other_coldkey=None):
        self._netuids = netuids
        self._network = network
        self._chunk_size = chunk_size
        self._other_coldkey = self._get_other_coldkey(other_coldkey)

        super().__init__()

    def _get_chk_hotkey(self):
        return RIZZO_CHK_HOTKEY

    def _get_subnet_data(self):
        asyncio.run(self._async_get_subnet_data())

    async def _get_validator_data(self, subtensor, block, netuids):
        if type(netuids) != list:
            netuids = [netuids]

        start_time = time.time()
        logger.info(f"Obtaining data for subnets: {netuids}")

        # Get a snapshot at the current block so everything is in sync
        snapshot = await subtensor.at(block)

        # Get mechanisms forfor all subnets.
        self._mech_splits = await asyncio.gather(
            *[self._get_mech_split(snapshot, netuid) for netuid in netuids]
        )

        # Get emission percentage for all subnets.
        self._subnet_emissions = await self._get_subnet_emissions(snapshot, netuids)

        # Get the metagraphs for all subnets.
        self._metagraphs = await asyncio.gather(
            *[self._get_metagraph(snapshot, netuid) for netuid in netuids]
        )

        # Get the last updated values for all mechids on all subnets.
        last_updates_results = await asyncio.gather(
            *[
                self._get_last_update(snapshot, netuid, mechid)
                for i, netuid in enumerate(netuids) for mechid in range(len(self._mech_splits[i]))
            ]
        )
        # Store the last_updates in a dictionary where the keys are the netuids and the values
        # are a list of last_updates for each mechid.
        self._last_updates_dict = {}
        ri = 0
        for ni, netuid in enumerate(netuids):
            last_updates_for_netuid = []
            for _ in range(len(self._mech_splits[ni])):
                last_updates_for_netuid.append(last_updates_results[ri])
                ri += 1
            self._last_updates_dict[netuid] = last_updates_for_netuid

        # Get the vtrust values for all subnets.
        self._vtrusts = await asyncio.gather(
            *[self._get_vtrust(snapshot, netuid)  for netuid in netuids]
        )

        if self._other_coldkey:
            self._children = [(True, [], '') for _ in netuids]
            self._children_pending = [([], 0) for _ in netuids]
            self._swap_child_hotkeys_dict = dict([(n, (0.0, "")) for n in netuids])
        else:
            # Get the list of child hotkeys for each netuid
            self._children = await asyncio.gather(
                *[self._get_children(snapshot, netuid) for netuid in netuids]
            )
            self._swap_child_hotkeys_dict = self._filter_swap_hotkeys()

            # Get the list of pending child hotkeys for each netuid
            self._children_pending = await asyncio.gather(
                *[self._get_pending_children(snapshot, netuid) for netuid in netuids]
            )

        # Get the take for each child hotkey on each netuid.
        self._chk_takes_dict = await self._get_child_hotkey_take_data(
            snapshot, netuids, False
        )

        # Get the take for each pending child hotkey on each netuid.
        self._chk_takes_pending_dict = await self._get_child_hotkey_take_data(
            snapshot, netuids, True
        )

        # Get the CHK take for all of our local swap hotkeys so we can ensure
        # that only the hotkeys on subnets that we own have 0% take. These will
        # be displayed next to the hotkeys in the Subnet Hotkeys tab on the
        # ValidatorStatus web page.
        async def dummy_chk_take_func():
            class DummyChkTake:
                value = 0
            return DummyChkTake()

        chk_take_func_calls = []
        for netuid in netuids:
            hotkey = RIZZO_HOTKEYS.get(netuid)
            if hotkey:
                chk_take_func_calls.append(
                    snapshot.query(
                        bittensor.storage.SubtensorModule.ChildkeyTake,
                        params=[hotkey, netuid]
                    )
                )
            else:
                chk_take_func_calls.append(dummy_chk_take_func())
        rizzo_hotkey_chk_takes_result = await asyncio.gather(*chk_take_func_calls)
        self._rizzo_hotkey_chk_takes = [
            t / bittensor.settings.U16_MAX for t in rizzo_hotkey_chk_takes_result
        ]

        # Get all of the rest of the data from the metagraph.
        for ni, netuid in enumerate(netuids):
            self._populate_validator_data_for_subnet(ni, netuid, block)

        total_time = time.time() - start_time
        logger.info(
            f"Data gathered in {int(total_time)} seconds for subnets: {netuids}."
        )

    def _filter_swap_hotkeys(self):
        swap_child_hotkeys = {}
        for i, child_hotkeys in enumerate(self._children):
            metagraph = self._metagraphs[i]
            swap_child_hotkeys[metagraph.netuid] = (0.0, "")

            uid = self._get_uid(metagraph)
            if uid is None:
                # Get our expected hotkey for the case in which we're not registered
                hotkey = RIZZO_HOTKEYS.get(metagraph.netuid)
            else:
                hotkey = metagraph.hotkeys[uid]

            for hotkey_element in child_hotkeys:
                if hotkey_element[1] == hotkey:
                    swap_child_hotkeys[metagraph.netuid] = hotkey_element
                    child_hotkeys.remove(hotkey_element)
                    break

        return swap_child_hotkeys

    async def _get_child_hotkey_take_data(self, subtensor, netuids, do_pending):
        # Get the take for each child hotkey on each netuid.
        chk_take_func_calls = []
        chk_take_funcs_dict = {}
        chk_takes_dict = {}
        func_call_index = 0
        for i, netuid in enumerate(netuids):
            if do_pending:
                child_hotkeys = self._children_pending[i]["children"]
            else:
                child_hotkeys = self._children[i]

            chk_take_funcs_dict[netuid] = []
            for _, child_hotkey in child_hotkeys:
                chk_take_func_calls.append(
                    subtensor.query(
                        bittensor.storage.SubtensorModule.ChildkeyTake,
                        params=[child_hotkey, netuid]
                    )
                )
                chk_take_funcs_dict[netuid].append(func_call_index)
                func_call_index += 1
        all_child_takes = (
            await asyncio.gather(*chk_take_func_calls)
            if chk_take_func_calls else []
        )
        all_child_takes = [t / bittensor.settings.U16_MAX for t in all_child_takes]

        # Massage the child take data to make it easier to obtain later on.
        for i, netuid in enumerate(netuids):
            cti = chk_take_funcs_dict.get(netuid)
            chk_takes_dict[netuid] = all_child_takes[cti[0]:cti[-1]+1] if cti else []

        return chk_takes_dict

    def _populate_validator_data_for_subnet(self, netuid_index, netuid, current_block):
        subnet_emission = self._subnet_emissions[netuid_index]
        subnet_mechs = self._mech_splits[netuid_index]
        metagraph = self._metagraphs[netuid_index]
        child_hotkeys = self._children[netuid_index]
        child_takes = self._chk_takes_dict.get(netuid, [])
        swap_child_hotkey = self._swap_child_hotkeys_dict[netuid]
        children_pending = self._children_pending[netuid_index]
        child_hotkeys_pending = children_pending["children"]
        chk_pending_block = children_pending["cooldown_block"]
        child_takes_pending = self._chk_takes_pending_dict.get(netuid, [])
        rizzo_hotkey_chk_take = self._rizzo_hotkey_chk_takes[netuid_index]
        last_updates = self._last_updates_dict[netuid]
        vtrust = self._vtrusts[netuid_index]
        subnet_alpha_price = metagraph.price
        subnet_tao_pool = round(metagraph.raw["tao_in"] / bittensor.settings.RAO_PER_TAO)

        # Get the hotkeys that we care about (Rizzo, Rt21, etc.)
        vali_hotkeys = {}
        rizzo_expected_hotkey = None
        for vali_name, vali_coldkey in COLDKEYS.items():
            if vali_name == "Rizzo":
                vali_uid = self._get_uid(metagraph)
                if vali_uid is None:
                    # Get our expected hotkey for the case in which we're not registered
                    rizzo_expected_hotkey = RIZZO_HOTKEYS.get(metagraph.netuid)
            else:
                vali_uid = self._get_other_vali_uid(metagraph, vali_coldkey)

            if vali_uid is None:
                vali_hotkeys[vali_name] = None
            else:
                vali_hotkeys[vali_name] = metagraph.hotkeys[vali_uid]
        validator_hotkeys = self.ValidatorHotkeys(**vali_hotkeys)

        # Get subnet tempo (used for determining bad Updated values)
        # subnet_tempo = subtensor.get_subnet_hyperparameters(netuid).tempo
        subnet_tempo = 360

        # Get Rizzo validator data
        rizzo_uid = self._get_uid(metagraph)
        if rizzo_uid is None:
            logger.warning(
                f"Rizzo validator not running on subnet {netuid}"
            )
            rizzo_vtrust = None
            rizzo_updated = None
            rizzo_last_update = None
        else:
            rizzo_vtrust = vtrust[rizzo_uid]
            rizzo_updated = [
                int(current_block - last_update[rizzo_uid]) for last_update in last_updates
            ]
            rizzo_last_update = [
                int(last_update[rizzo_uid]) for last_update in last_updates
            ]

        # Get child hotkey data
        chk_fraction = 0.0
        child_hotkey_data = []
        if len(child_hotkeys) == 0:
            chk_vtrust = None
            chk_updated = None
        else:
            chk_vtrust = 0.0
            chk_updated = [0] * len(subnet_mechs)
            for i, (child_fraction, child_hotkey) in enumerate(child_hotkeys):
                child_take = child_takes[i]
                try:
                    child_uid = metagraph.hotkeys.index(child_hotkey)
                except ValueError:
                    child_vtrust = None
                    child_updated = None
                else:
                    child_vtrust = float(vtrust[child_uid])
                    child_updated = [
                        int(current_block - last_update[child_uid]) for last_update in last_updates
                    ]

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
                if child_updated is not None:
                    for mi in range(len(subnet_mechs)) :
                        if child_updated[mi] > chk_updated[mi]:
                            chk_updated[mi] = child_updated[mi]

            chk_vtrust /= chk_fraction

        # Get missing CHK amount for subnets with swap hotkeys
        if validator_hotkeys.Rizzo and validator_hotkeys.Rizzo == self._get_chk_hotkey():
            missing_chk = 0.0
        else:
            swap_chk_fraction = swap_child_hotkey[0]  # if swap_child_hotkey else 0.0
            missing_chk = 1.0 - chk_fraction - swap_chk_fraction

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
                    child_vtrust = float(vtrust[child_uid])
                    child_updated = [
                        int(current_block - last_update[child_uid]) for last_update in last_updates
                    ]

                pending_child_hotkey_data.append(
                    self.ChildHotkeyData(
                        fraction=child_fraction,
                        hotkey=child_hotkey,
                        take=child_take,
                        vtrust=child_vtrust,
                        updated=child_updated,
                    )
                )

        # Get all validator uids that have validator permits.
        all_uids = [v.uid for v in metagraph.validators if v.uid != rizzo_uid]
        num_total_validators = len(all_uids)

        # Get all validators that have proper VT and U
        valid_uids_vtrust = [u for u in all_uids if (vtrust[u] > MIN_VTRUST_THRESHOLD)]
        valid_uids = [
            [u for u in valid_uids_vtrust if (current_block - last_update[u] < MAX_U_THRESHOLD)]  
            for last_update in last_updates
        ]

        valid_uids_all = numpy.unique(numpy.concatenate(valid_uids))
        num_valid_validators = len(valid_uids_all)

        if rizzo_uid is not None:
            num_total_validators += 1
            if (
                rizzo_vtrust is not None and rizzo_vtrust > MIN_VTRUST_THRESHOLD
                and rizzo_updated is not None and any([ri < MAX_U_THRESHOLD for ri in rizzo_updated])
            ):
                num_valid_validators += 1

        # Get rt21 vTrust and gap between rizzo and rt21
        rt21_uid = self._get_other_vali_uid(metagraph, COLDKEYS["Rt21"])
        rt21_vtrust = vtrust[rt21_uid] if rt21_uid is not None else None

        if rt21_vtrust is None:
            rt21_vtrust_gap = None
        elif rizzo_vtrust is None:
            rt21_vtrust_gap = rt21_vtrust
        else:
            rt21_vtrust_gap = rt21_vtrust - rizzo_vtrust

        # Get tao.com vTrust and gap between rizzo and tao.com
        taocom_uid = self._get_other_vali_uid(metagraph, COLDKEYS["TAO_com"])
        taocom_vtrust = vtrust[taocom_uid] if taocom_uid is not None else None

        if taocom_vtrust is None:
            taocom_vtrust_gap = None
        elif rizzo_vtrust is None:
            taocom_vtrust_gap = taocom_vtrust
        else:
            taocom_vtrust_gap = taocom_vtrust - rizzo_vtrust

        # Get yuma vTrust and gap between rizzo and yuma
        yuma_uid = self._get_other_vali_uid(metagraph, COLDKEYS["Yuma"])
        yuma_vtrust = vtrust[yuma_uid] if yuma_uid is not None else None

        if yuma_vtrust is None:
            yuma_vtrust_gap = None
        elif rizzo_vtrust is None:
            yuma_vtrust_gap = yuma_vtrust
        else:
            yuma_vtrust_gap = yuma_vtrust - rizzo_vtrust

        # Get other validator data
        if not len(valid_uids_all):
            max_vtrust = None
            avg_vtrust = None
            min_vtrust = None
            min_updated = None
            avg_updated = None
            max_updated = None
        else:
            # Get min/max/average vTrust values.
            vtrusts = [vtrust[u] for u in valid_uids_all]
            max_vtrust = float(numpy.max(vtrusts))
            avg_vtrust = float(numpy.average(vtrusts))
            min_vtrust = float(numpy.min(vtrusts))

            # Get min/max/average Updated values.
            updateds = [
                [current_block - last_updates[i][u] for u in valid_uids[i]]
                for i in range(len(last_updates))
            ]
            min_updated = [int(numpy.min(u)) for u in updateds]
            avg_updated = [int(numpy.round(numpy.average(u))) for u in updateds]
            max_updated = [int(numpy.max(u)) for u in updateds]

        # Store the data.
        self._validator_data[netuid] = self.ValidatorData(
            block=current_block,
            netuid=netuid,
            subnet_emission=subnet_emission,
            subnet_alpha_price=subnet_alpha_price,
            subnet_tao_pool=subnet_tao_pool,
            subnet_mechs=subnet_mechs,
            subnet_tempo=subnet_tempo,
            num_total_validators=num_total_validators,
            num_valid_validators=num_valid_validators,
            rizzo_last_update=rizzo_last_update,
            rizzo_vtrust=rizzo_vtrust,
            rt21_vtrust=rt21_vtrust,
            rt21_vtrust_gap=rt21_vtrust_gap,
            taocom_vtrust=taocom_vtrust,
            taocom_vtrust_gap=taocom_vtrust_gap,
            yuma_vtrust=yuma_vtrust,
            yuma_vtrust_gap=yuma_vtrust_gap,
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
            missing_chk=missing_chk,
            chk_pending_block=chk_pending_block,
            chk_pending_time=chk_pending_time,
            child_hotkey_data=child_hotkey_data,
            pending_child_hotkey_data=pending_child_hotkey_data,
            validator_hotkeys=validator_hotkeys,
            rizzo_expected_hotkey=rizzo_expected_hotkey,
            rizzo_hotkey_chk_take=rizzo_hotkey_chk_take,
        )
