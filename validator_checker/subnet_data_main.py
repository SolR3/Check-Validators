# Future imports
from __future__ import annotations

# standart imports
import asyncio
from collections import defaultdict
from dataclasses import dataclass, make_dataclass
import numpy
import time

# bittensor import
import bittensor

# Local imports
from .constants import (
    OWNED_SUBNETS,
    MIN_VTRUST_THRESHOLD,
    MAX_U_THRESHOLD,
    COLDKEYS,
    RIZZO_CHK_HOTKEY,
    RIZZO_HOTKEYS,
    RIZZO_OWNED_COLDKEYS,
)
from .subnet_data_base import SubnetDataFromSubtensor
from .utils import logger


class SubnetDataMain(SubnetDataFromSubtensor):
    @dataclass
    class ValidatorData:
        block: int
        netuid: int
        is_owned_subnet: bool
        subnet_emission: float
        subnet_alpha_price: float
        subnet_tao_pool: int
        subnet_mechs: list[int]
        subnet_tempo: int
        subnet_validator_activity_cutoff: int
        num_total_validators: int
        num_valid_validators: int
        rizzo_emission: float
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
        rizzo_delegate_take: float | None
        rizzo_hotkey: str | None
        rizzo_hotkey_total_alpha: float | None
        rizzo_own_alpha: float | None
        rizzo_parents: list[SubnetDataMain.ParentHotkeyData] | None
        rizzo_emission_block: int | None
        rizzo_hotkey_root_stake: float | None
        rizzo_chk_hotkey_total_alpha: float | None
        rizzo_chk_hotkey_own_alpha: float | None
        rizzo_own_root_stake: float | None
        rizzo_chk_hotkey_own_root_stake: float | None
        rizzo_hotkey_children_fraction: float | None
        rizzo_chk_hotkey_delegate_take: float | None
        rizzo_chk_hotkey_on_root: bool | None
        rizzo_chk_hotkey_alpha_dividends: float | None
        rizzo_chk_hotkey_root_dividends: float | None
        rizzo_hotkey_on_root: bool | None
        rizzo_hotkey_alpha_dividends: float | None
        rizzo_hotkey_root_dividends: float | None
        rizzo_hotkey_child_data: list[SubnetDataMain.ChildHotkeyData] | None

    @dataclass
    class ChildHotkeyData:
        fraction: float
        hotkey: str
        take: float
        vtrust: float
        updated: list[int]
        # The income fields are only populated for active child hotkeys.
        emission: float | None = None
        emission_block: int | None = None
        total_alpha: float | None = None
        root_stake: float | None = None
        children_fraction: float | None = None
        parents: list[SubnetDataMain.ParentHotkeyData] | None = None
        on_root: bool | None = None

    @dataclass
    class ParentHotkeyData:
        hotkey: str
        proportion: float
        alpha_stake: float
        root_stake: float
        on_root: bool

    ValidatorHotkeys = make_dataclass(
        "ValidatorHotkeys", [(k, str) for k in COLDKEYS]
    )

    def __init__(self, network, netuids=None, chunk_size=0, other_coldkey=None):
        self._netuids = netuids
        self._network = network
        self._chunk_size = chunk_size
        self._other_coldkey = self._get_other_coldkey(other_coldkey)

        self._global_data = {}

        super().__init__()

    @property
    def global_data(self):
        return self._global_data

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

        # Get the validator activity cutoff for all subnets.
        self._subnet_validator_activity_cutoffs = await asyncio.gather(
            *[self._get_validator_activity_cutoff(snapshot, netuid) for netuid in netuids]
        )

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
            self._children = [[] for _ in netuids]
            self._children_pending = [{"children": [], "cooldown_block": 0} for _ in netuids]
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

        # Get the network wide values used to calculate income.
        ck_burn, tao_weight = await asyncio.gather(
            snapshot.query(bittensor.storage.SubtensorModule.CKBurn),
            snapshot.query(bittensor.storage.SubtensorModule.TaoWeight),
        )
        self._global_data = {
            "ck_burn": ck_burn / (2**64 - 1),
            "tao_weight": tao_weight / (2**64 - 1),
        }

        # Get the alpha staked by our own coldkeys on each hotkey and netuid.
        own_coldkeys = [self._other_coldkey] if self._other_coldkey else RIZZO_OWNED_COLDKEYS
        stake_positions = await snapshot.staking.stake_for_coldkeys(own_coldkeys)
        own_alpha_rao = defaultdict(int)
        for positions in stake_positions.values():
            for position in positions:
                own_alpha_rao[(position.hotkey, position.netuid)] += position.stake.rao

        # Get the data needed to calculate what we keep of rizzo_emission.
        self._rizzo_income_data = await asyncio.gather(
            *[
                self._get_rizzo_income_data(
                    snapshot, metagraph, own_alpha_rao, self._vtrusts[i], block
                )
                for i, metagraph in enumerate(self._metagraphs)
            ]
        )

        # Get the data needed to calculate what we earn as a parent of each child hotkey.
        self._child_income_data = await asyncio.gather(
            *[
                asyncio.gather(
                    *[
                        self._get_child_income_data(snapshot, child_hotkey, netuid)
                        for _, child_hotkey in self._children[i]
                    ]
                )
                for i, netuid in enumerate(netuids)
            ]
        )

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

    @staticmethod
    async def _is_on_root(subtensor, hotkey):
        root_uid = await subtensor.query(
            bittensor.storage.SubtensorModule.Uids,
            params=[0, hotkey]
        )
        return root_uid is not None

    @staticmethod
    async def _get_dividends(subtensor, hotkey, netuid):
        # What the hotkey was paid in the last epoch, in alpha and after its delegate take.
        alpha_dividends, root_dividends = await asyncio.gather(
            subtensor.query(
                bittensor.storage.SubtensorModule.AlphaDividendsPerSubnet,
                params=[netuid, hotkey]
            ),
            subtensor.query(
                bittensor.storage.SubtensorModule.RootAlphaDividendsPerSubnet,
                params=[netuid, hotkey]
            ),
        )
        return (
            (alpha_dividends or 0) / bittensor.settings.RAO_PER_TAO,
            (root_dividends or 0) / bittensor.settings.RAO_PER_TAO,
        )

    async def _get_chk_hotkey_income_data(self, subtensor, netuid, own_alpha_rao):
        if self._other_coldkey:
            return {
                "rizzo_chk_hotkey_total_alpha": None,
                "rizzo_chk_hotkey_own_alpha": None,
                "rizzo_chk_hotkey_own_root_stake": None,
                "rizzo_chk_hotkey_delegate_take": None,
                "rizzo_chk_hotkey_on_root": None,
                "rizzo_chk_hotkey_alpha_dividends": None,
                "rizzo_chk_hotkey_root_dividends": None,
            }

        chk_hotkey = self._get_chk_hotkey()
        total_alpha, delegate_take, on_root, (alpha_dividends, root_dividends) = await asyncio.gather(
            subtensor.query(
                bittensor.storage.SubtensorModule.TotalHotkeyAlpha,
                params=[chk_hotkey, netuid]
            ),
            subtensor.delegation.delegate_take(chk_hotkey),
            self._is_on_root(subtensor, chk_hotkey),
            self._get_dividends(subtensor, chk_hotkey, netuid),
        )

        return {
            "rizzo_chk_hotkey_total_alpha": total_alpha / bittensor.settings.RAO_PER_TAO,
            "rizzo_chk_hotkey_own_alpha": own_alpha_rao[(chk_hotkey, netuid)] / bittensor.settings.RAO_PER_TAO,
            "rizzo_chk_hotkey_own_root_stake": own_alpha_rao[(chk_hotkey, 0)] / bittensor.settings.RAO_PER_TAO,
            "rizzo_chk_hotkey_delegate_take": delegate_take["take"],
            "rizzo_chk_hotkey_on_root": on_root,
            "rizzo_chk_hotkey_alpha_dividends": alpha_dividends,
            "rizzo_chk_hotkey_root_dividends": root_dividends,
        }

    @staticmethod
    def _get_child_hotkey_status(metagraph, child_hotkey, vtrust, last_updates, current_block):
        try:
            child_uid = metagraph.hotkeys.index(child_hotkey)
        except ValueError:
            return None, None, None

        child_vtrust = float(vtrust[child_uid])
        child_updated = [
            int(current_block - last_update[child_uid]) for last_update in last_updates
        ]
        child_emission = metagraph.neurons[child_uid].emission.alpha
        return child_vtrust, child_updated, child_emission

    async def _get_rizzo_hotkey_child_data(self, subtensor, metagraph, children, vtrust, current_block):
        netuid = metagraph.netuid
        takes, income_data = await asyncio.gather(
            asyncio.gather(
                *[
                    subtensor.query(
                        bittensor.storage.SubtensorModule.ChildkeyTake,
                        params=[child_hotkey, netuid]
                    )
                    for _, child_hotkey in children
                ]
            ),
            asyncio.gather(
                *[
                    self._get_child_income_data(subtensor, child_hotkey, netuid)
                    for _, child_hotkey in children
                ]
            ),
        )

        child_data = []
        for i, (proportion, child_hotkey) in enumerate(children):
            child_vtrust, child_updated, child_emission = self._get_child_hotkey_status(
                metagraph, child_hotkey, vtrust, self._last_updates_dict[netuid], current_block
            )
            child_data.append(
                self.ChildHotkeyData(
                    fraction=proportion / (2**64 - 1),
                    hotkey=child_hotkey,
                    take=takes[i] / bittensor.settings.U16_MAX,
                    vtrust=child_vtrust,
                    updated=child_updated,
                    emission=child_emission,
                    **income_data[i],
                )
            )
        return child_data

    async def _get_rizzo_income_data(self, subtensor, metagraph, own_alpha_rao, vtrust, current_block):
        netuid = metagraph.netuid

        # Our CHK hotkey holds stake and earns even on subnets on which we're not
        # registered, so its data is populated regardless of whether we have a uid.
        chk_data = await self._get_chk_hotkey_income_data(subtensor, netuid, own_alpha_rao)

        uid = self._get_uid(metagraph)
        if uid is None:
            return {
                "rizzo_delegate_take": None,
                "rizzo_hotkey": None,
                "rizzo_hotkey_total_alpha": None,
                "rizzo_own_alpha": None,
                "rizzo_parents": None,
                "rizzo_emission_block": None,
                "rizzo_hotkey_root_stake": None,
                "rizzo_own_root_stake": None,
                "rizzo_hotkey_children_fraction": None,
                "rizzo_hotkey_on_root": None,
                "rizzo_hotkey_alpha_dividends": None,
                "rizzo_hotkey_root_dividends": None,
                "rizzo_hotkey_child_data": None,
                **chk_data,
            }

        # The delegate take is set per hotkey and we can use a different hotkey
        # on each subnet, so always read it for the hotkey on this subnet.
        hotkey = metagraph.hotkeys[uid]
        (
            delegate_take, children, total_alpha, root_stake, rizzo_parents, emission_block,
            on_root, (alpha_dividends, root_dividends)
        ) = await asyncio.gather(
            subtensor.delegation.delegate_take(hotkey),
            subtensor.delegation.children(hotkey, netuid),
            subtensor.query(
                bittensor.storage.SubtensorModule.TotalHotkeyAlpha,
                params=[hotkey, netuid]
            ),
            subtensor.query(
                bittensor.storage.SubtensorModule.TotalHotkeyAlpha,
                params=[hotkey, 0]
            ),
            self._get_parent_hotkey_data(subtensor, hotkey, netuid),
            subtensor.query(
                bittensor.storage.SubtensorModule.LastMechansimStepBlock,
                params=[netuid]
            ),
            self._is_on_root(subtensor, hotkey),
            self._get_dividends(subtensor, hotkey, netuid),
        )

        rizzo_hotkey_child_data = await self._get_rizzo_hotkey_child_data(
            subtensor, metagraph, children, vtrust, current_block
        )

        return {
            "rizzo_delegate_take": delegate_take["take"],
            "rizzo_hotkey": hotkey,
            "rizzo_hotkey_total_alpha": total_alpha / bittensor.settings.RAO_PER_TAO,
            "rizzo_own_alpha": own_alpha_rao[(hotkey, netuid)] / bittensor.settings.RAO_PER_TAO,
            "rizzo_parents": rizzo_parents,
            "rizzo_emission_block": emission_block or None,
            "rizzo_hotkey_root_stake": root_stake / bittensor.settings.RAO_PER_TAO,
            "rizzo_own_root_stake": own_alpha_rao[(hotkey, 0)] / bittensor.settings.RAO_PER_TAO,
            "rizzo_hotkey_children_fraction": sum(c[0] for c in children) / (2**64 - 1),
            "rizzo_hotkey_on_root": on_root,
            "rizzo_hotkey_alpha_dividends": alpha_dividends,
            "rizzo_hotkey_root_dividends": root_dividends,
            "rizzo_hotkey_child_data": rizzo_hotkey_child_data,
            **chk_data,
        }

    async def _get_child_income_data(self, subtensor, hotkey, netuid):
        total_alpha, root_stake, children, parents, emission_block, on_root = await asyncio.gather(
            subtensor.query(
                bittensor.storage.SubtensorModule.TotalHotkeyAlpha,
                params=[hotkey, netuid]
            ),
            subtensor.query(
                bittensor.storage.SubtensorModule.TotalHotkeyAlpha,
                params=[hotkey, 0]
            ),
            subtensor.delegation.children(hotkey, netuid),
            self._get_parent_hotkey_data(subtensor, hotkey, netuid),
            subtensor.query(
                bittensor.storage.SubtensorModule.LastMechansimStepBlock,
                params=[netuid]
            ),
            self._is_on_root(subtensor, hotkey),
        )

        return {
            "emission_block": emission_block or None,
            "total_alpha": total_alpha / bittensor.settings.RAO_PER_TAO,
            "root_stake": root_stake / bittensor.settings.RAO_PER_TAO,
            "children_fraction": sum(c[0] for c in children) / (2**64 - 1),
            "parents": parents,
            "on_root": on_root,
        }

    async def _get_parent_hotkey_data(self, subtensor, hotkey, netuid):
        parents = await subtensor.delegation.parents(hotkey, netuid)

        parent_stakes = await asyncio.gather(
            *[
                subtensor.query(
                    bittensor.storage.SubtensorModule.TotalHotkeyAlpha,
                    params=[parent_hotkey, stake_netuid]
                )
                for _, parent_hotkey in parents for stake_netuid in (netuid, 0)
            ]
        )
        parents_on_root = await asyncio.gather(
            *[self._is_on_root(subtensor, parent_hotkey) for _, parent_hotkey in parents]
        )

        return [
            self.ParentHotkeyData(
                hotkey=parent_hotkey,
                proportion=proportion / (2**64 - 1),
                alpha_stake=parent_stakes[2 * i] / bittensor.settings.RAO_PER_TAO,
                root_stake=parent_stakes[2 * i + 1] / bittensor.settings.RAO_PER_TAO,
                on_root=parents_on_root[i],
            )
            for i, (proportion, parent_hotkey) in enumerate(parents)
        ]

    def _populate_validator_data_for_subnet(self, netuid_index, netuid, current_block):
        is_owned_subnet = netuid in OWNED_SUBNETS
        subnet_emission = self._subnet_emissions[netuid_index]
        subnet_mechs = self._mech_splits[netuid_index]
        subnet_validator_activity_cutoff = self._subnet_validator_activity_cutoffs[netuid_index]
        metagraph = self._metagraphs[netuid_index]
        child_hotkeys = self._children[netuid_index]
        child_takes = self._chk_takes_dict.get(netuid, [])
        child_income_data = self._child_income_data[netuid_index]
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
        subnet_tempo = metagraph.tempo

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

        # Get Rizzo validator data
        rizzo_uid = self._get_uid(metagraph)
        if rizzo_uid is None:
            logger.warning(
                f"Rizzo validator not running on subnet {netuid}"
            )
            rizzo_emission = None
            rizzo_vtrust = None
            rizzo_updated = None
            rizzo_last_update = None
        else:
            # The emission.alpha value is in alpha units (rao -> alpha). It is the gross emission
            # for the last epoch, before the delegate take, nominators and child/parent splits.
            rizzo_emission = metagraph.neurons[rizzo_uid].emission.alpha
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
                child_vtrust, child_updated, child_emission = self._get_child_hotkey_status(
                    metagraph, child_hotkey, vtrust, last_updates, current_block
                )

                child_hotkey_data.append(
                    self.ChildHotkeyData(
                        fraction=child_fraction,
                        hotkey=child_hotkey,
                        take=child_take,
                        vtrust=child_vtrust,
                        updated=child_updated,
                        emission=child_emission,
                        **child_income_data[i],
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

        valid_uids_all = numpy.unique(numpy.concatenate(valid_uids)).astype(int)
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
            min_updated = [int(numpy.min(u)) if u else None for u in updateds]
            avg_updated = [int(numpy.round(numpy.average(u))) if u else None for u in updateds]
            max_updated = [int(numpy.max(u)) if u else None for u in updateds]

        # Store the data.
        self._validator_data[netuid] = self.ValidatorData(
            block=current_block,
            netuid=netuid,
            is_owned_subnet=is_owned_subnet,
            subnet_emission=subnet_emission,
            subnet_alpha_price=subnet_alpha_price,
            subnet_tao_pool=subnet_tao_pool,
            subnet_mechs=subnet_mechs,
            subnet_tempo=subnet_tempo,
            subnet_validator_activity_cutoff=subnet_validator_activity_cutoff,
            num_total_validators=num_total_validators,
            num_valid_validators=num_valid_validators,
            rizzo_emission=rizzo_emission,
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
            **self._rizzo_income_data[netuid_index],
        )
