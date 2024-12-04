# bittensor import
import bittensor

# standard imports
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
import numpy
import threading
import time


TOTAL_EMISSION = 295.5 # TODO - Need some way to verify this
MIN_STAKE_THRESHOLD = 5000 # TODO - Need some way to verify this


class SubnetData:
    ValidatorData = namedtuple(
    "ValidatorData", [
        "netuid",
        "subnet_emission",
        "subnet_tempo",
        "num_validators",
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

    # constants
    _rizzo_hotkey = "5F2CsUDVbRbVMXTh9fAzF9GacjVX7UapvRxidrxe7z8BYckQ"

    def __init__(self, netuids, network, threads, debug):
        self._netuids = netuids
        self._network = network
        self._threads = threads
        self._debug = debug

        self._validator_data_lock = threading.Lock()
        self._validator_data = {}

        # Get subtensor and list of netuids.
        self._subtensor = bittensor.subtensor(network=self._network)

        # Gather the data for all given subnets
        self._get_subnet_data()

    @property
    def validator_data(self):
        return self._validator_data
    
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
                with ThreadPoolExecutor(max_workers=self._threads) as executor:
                    executor.map(self._get_validator_data,
                        netuids, [True for _ in range(len(netuids))])
            else:
                for netuid in netuids:
                    self._get_validator_data(netuid, False)

            # Get netuids missing data
            netuids = list(set(netuids).difference(set(self._validator_data)))
            if netuids:
                self._print_debug("\nFailed to gather data for subnets: "
                                 f"{', '.join([str(n) for n in netuids])}.")
            else:
                break

    def _get_validator_data(self, netuid, init_new_subtensor):
        start_time = time.time()
        self._print_debug(f"\nObtaining data for subnet {netuid}\n")

        # When threading, re-get subtensor for obtaining the updated values.
        # The subtensor object can't seem to handle multiple threads calling
        # the blocks_since_last_update() method at the same time.
        subtensor = bittensor.subtensor(network=self._network) \
                        if init_new_subtensor \
                            else self._subtensor

        # Get metagraph for the subnet.
        metagraph = subtensor.metagraph(netuid=netuid)
    
        # Get emission percentage for the subnet.
        subnet_emission = numpy.sum(metagraph.E) / TOTAL_EMISSION * 100

        # Get subnet tempo (used for determining bad Updated values)
        subnet_tempo = subtensor.get_subnet_hyperparameters(netuid).tempo

        # Get UID for Rizzo.
        try:
            rizzo_uid = metagraph.hotkeys.index(self._rizzo_hotkey)
        except ValueError:
            self._print_debug("\nWARNING: Rizzo validator not running on subnet "
                 f"{netuid}")
            with self._validator_data_lock:
                self._validator_data[netuid] = self.ValidatorData(
                    netuid=netuid,
                    subnet_emission=subnet_emission,
                    subnet_tempo=None,
                    num_validators=None,
                    rizzo_stake_rank=None,
                    rizzo_emission=None,
                    rizzo_vtrust=None,
                    max_vtrust=None,
                    avg_vtrust=None,
                    min_vtrust=None,
                    rizzo_updated=None,
                    min_updated=None,
                    avg_updated=None,
                    max_updated=None,)
            return
        
        # Get Rizzo validator values
        rizzo_emission = metagraph.E[rizzo_uid]
        rizzo_vtrust = metagraph.Tv[rizzo_uid]
        rizzo_updated = subtensor.blocks_since_last_update(
            netuid=netuid, uid=rizzo_uid)

        # Get all validators that have a valid stake amount.
        valid_uids = [i for (i, s) in enumerate(metagraph.S)
                      if i != rizzo_uid and s > MIN_STAKE_THRESHOLD]
        num_validators = len(valid_uids) + 1

        # Get stake-wise ranking for Rizzo
        rizzo_stake = metagraph.S[rizzo_uid]
        rizzo_stake_rank = (
            len(metagraph.S) - sorted(metagraph.S).index(rizzo_stake))

        # Get min/max/average vTrust values.
        vtrusts = [metagraph.Tv[uid] for uid in valid_uids]
        max_vtrust = numpy.max(vtrusts)
        avg_vtrust = numpy.average(vtrusts)
        min_vtrust = numpy.min(vtrusts)

        # Get min/max/average Updated values.
        updateds = []
        for uid in valid_uids:
            updateds.append(subtensor.blocks_since_last_update(
                netuid=netuid, uid=uid))
        min_updated = numpy.min(updateds)
        avg_updated = int(numpy.round(numpy.average(updateds)))
        max_updated = numpy.max(updateds)

        # Store the data.
        with self._validator_data_lock:
            self._validator_data[netuid] = self.ValidatorData(
                netuid=netuid,
                subnet_emission=subnet_emission,
                subnet_tempo=subnet_tempo,
                num_validators=num_validators,
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
        
        total_time = time.time() - start_time
        self._print_debug(f"\nSubnet {netuid} data gathered in "
                         f"{int(total_time)} seconds.")

    def _print_debug(self, message):
        if self._debug:
            print(message)
