# standard imports
import json
import os
import tempfile
import time

# bittensor import
import bittensor

# Local imports
from json_writer_base import JsonWriterBase, LoopRunnerBase
from subnet_data_intervals import (
    SubnetDataIntervals,
    SubnetDataIntervalsFromJson
)
from constants import DATA_FILE_NAME
import utils


class LoopRunnerIntervals(LoopRunnerBase):
    def __init__(self, run_func, options):
        options.archive_network = options.local_archive_subtensor or "archive"        
        super().__init__(run_func, options)

    def _makedirs(self):
        os.makedirs(self._options.json_folder, exist_ok=True)


class JsonWriterIntervals(JsonWriterBase):
    def __init__(self, options):
        self._archive_network = options.archive_network
        self._chunk_size = options.chunk_size
        self._num_weights_intervals = options.num_weights_intervals
        self._json_folder = options.json_folder

        super().__init__(options)

    def _create_tmp(self):
        # Make tmpdir for writing json files.
        self._tempdir = tempfile.mkdtemp(prefix="write_interval_data_")

    def _write_json_files_to_tmp(self):
        bittensor.logging.info("Gathering subnet intervals data.")
        start_time = time.time()

        existing_json_data = SubnetDataIntervalsFromJson(
            self._netuids, self._json_folder
        ).validator_data

        new_data_dict = SubnetDataIntervals(
            self._netuids,
            self._num_weights_intervals,
            self._archive_network,
            chunk_size=self._chunk_size,
            existing_data=existing_json_data
        ).as_dict()

        for netuid in self._netuids:
            json_file_name = utils.get_json_file_name(DATA_FILE_NAME, netuid)
            write_json_file = os.path.join(self._tempdir, json_file_name)
            bittensor.logging.info(f"Writing data to file: {write_json_file}")
            with open(write_json_file, "w") as fp:
                json.dump({netuid: new_data_dict[netuid]}, fp, indent=4)

        total_time = round(time.time() - start_time)
        bittensor.logging.info(
            f"Subnet data gathering took {utils.get_formatted_time(total_time)} "
            f"for subnets {self._netuids}."
        )

    def _mv_tmp_to_final(self):
        # Move files over to final location and write timestamp.
        self._move_json_files_to_final_dir(self._tempdir, self._json_folder)
        self._write_timestamp(self._json_folder, DATA_FILE_NAME)
