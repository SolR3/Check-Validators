# standard imports
import json
import os
import tempfile
import time

# bittensor import
import bittensor

# Local imports
from json_writer_base import JsonWriterBase, LoopRunnerBase
from subnet_data_main import SubnetDataMain
from subnet_data_intervals import SubnetDataIntervalsFromMainData
import utils
from constants import DATA_FILE_NAME


class LoopRunnerMain(LoopRunnerBase):
    def _makedirs(self):
        os.makedirs(self._options.json_main_folder, exist_ok=True)
        if self._options.json_intervals_folder:
            os.makedirs(self._options.json_intervals_folder, exist_ok=True)


class JsonWriterMain(JsonWriterBase):
    def __init__(self, options):
        self._chunk_size = options.chunk_size
        self._num_weights_intervals = options.num_weights_intervals
        self._json_main_folder = options.json_main_folder
        self._json_intervals_folder = options.json_intervals_folder

        super().__init__(options)

    def _create_tmp(self):
        # Make tmpdir for writing json files.
        self._tempdir_main = tempfile.mkdtemp(prefix="write_vali_data_main_")
        if self._json_intervals_folder:
            self._tempdir_intervals = tempfile.mkdtemp(prefix="write_vali_data_intervals_")
        else:
            self._tempdir_intervals = None

    def _write_json_files_to_tmp(self):
        bittensor.logging.info("Gathering subnet data.")
        start_time = time.time()

        # TODO - Some refactoring is needed so we can get the data object
        # from SubnetDataMain and then call as_dict() to get the main data
        # and some new intervals calculation method to get the most recent
        # interval.

        # Gather subnet data
        validator_data_main = SubnetDataMain(
            self._netuids,
            self._lite_network,
            chunk_size=self._chunk_size,
        ).as_dict()

        # Write main data json file
        netuid_range = f"{self._netuids[0]}-{self._netuids[-1]}"        
        json_file_name_main = utils.get_json_file_name(DATA_FILE_NAME, netuid_range)
        json_file_main = os.path.join(self._tempdir_main, json_file_name_main)

        bittensor.logging.info(f"Writing main data to file: {json_file_main}")
        with open(json_file_main, "w") as fp:
            json.dump(validator_data_main, fp, indent=4)

        # If the --json-intervals-folder was specified then gather the intervals from
        # the existing json files and add interval blocks as necessary.
        if self._json_intervals_folder:
            validator_data_intervals = SubnetDataIntervalsFromMainData(
                self._netuids, validator_data_main, self._json_intervals_folder,
                num_intervals=self._num_weights_intervals
            ).as_dict()

            for netuid in self._netuids:
                json_file_name_intervals = \
                    utils.get_json_file_name(DATA_FILE_NAME, netuid)
                json_file_intervals = os.path.join(
                    self._tempdir_intervals, json_file_name_intervals)
                bittensor.logging.info(f"Writing intervals data for netuid {netuid} to file: "
                      f"{json_file_intervals}")
                with open(json_file_intervals, "w") as fp:
                    json.dump({netuid: validator_data_intervals[netuid]}, fp, indent=4)

        total_time = round(time.time() - start_time)
        bittensor.logging.info(
            f"Subnet data gathering took {utils.get_formatted_time(total_time)}."
        )

    def _mv_tmp_to_final(self):
        # Move files over to final location and write timestamp.
        self._move_json_files_to_final_dir(self._tempdir_main, self._json_main_folder)
        self._write_timestamp(self._json_main_folder, DATA_FILE_NAME)

        if self._json_intervals_folder:
            self._move_json_files_to_final_dir(self._tempdir_intervals, self._json_intervals_folder)
            self._write_timestamp(self._json_intervals_folder, DATA_FILE_NAME)
