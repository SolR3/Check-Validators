# standard imports
import os
import shutil
import tempfile
import time

# Local imports
from .constants import DATA_FILE_NAME
from .json_writer_base import (
    JsonWriterBase,
    LoopRunnerBase,
    mp_queue,
)
from .subnet_data_main import SubnetDataMain
from .subnet_data_intervals import SubnetDataIntervalsFromMainData
from .utils import (
    get_formatted_time,
    get_json_file_name_for_netuid,
    logger,
    SubtensorConnectionError,
)


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

    def _mk_tempdirs(self):
        # Make tmpdir for writing json files.
        self._tempdir_main = tempfile.mkdtemp(prefix="write_vali_data_main_")
        tempdirs = [self._tempdir_main]
        if self._json_intervals_folder:
            self._tempdir_intervals = tempfile.mkdtemp(prefix="write_vali_data_intervals_")
            tempdirs.append(self._tempdir_intervals)
        else:
            self._tempdir_intervals = None
        mp_queue.put(tempdirs)

    def _write_json_files_to_tmp(self):
        logger.info("Gathering subnet data.")
        start_time = time.time()

        # Gather subnet data.
        # This assumes that there are no bugs in SubnetDataMain and
        # any exceptions raised are due to subtensor connection errors.
        try:
            subnet_data = SubnetDataMain(
                self._lite_network,
                chunk_size=self._chunk_size,
            )
        except Exception as err:
            logger.error(f"Subtensor connection failed on '{self._lite_network}'")
            logger.error(f"{type(err).__name__}: {err}")
            raise SubtensorConnectionError

        validator_data_main = subnet_data.as_dict
        netuids = subnet_data.netuids

        # Write main data json file
        json_file_main = os.path.join(self._tempdir_main, DATA_FILE_NAME)

        logger.info(f"Writing main data to file: {json_file_main}")
        self._write_json_with_timestamp(validator_data_main, json_file_main)

        # If the --json-intervals-folder was specified then gather the intervals from
        # the existing json files and add interval blocks as necessary.
        if self._json_intervals_folder:
            validator_data_intervals = SubnetDataIntervalsFromMainData(
                netuids, validator_data_main, self._json_intervals_folder,
                num_intervals=self._num_weights_intervals
            ).as_dict

            for netuid in netuids:
                json_file_name_intervals = get_json_file_name_for_netuid(DATA_FILE_NAME, netuid)
                json_file_intervals = os.path.join(
                    self._tempdir_intervals, json_file_name_intervals)
                logger.info(f"Writing intervals data for netuid {netuid} to file: "
                      f"{json_file_intervals}")
                self._write_json_with_timestamp(
                    validator_data_intervals[netuid], json_file_intervals
                )

        total_time = round(time.time() - start_time)
        logger.info(
            f"Subnet data gathering took {get_formatted_time(total_time)}."
        )

    def _mv_tmp_to_final(self):
        # Move files over to final location.
        self._move_json_files_to_final_dir(self._tempdir_main, self._json_main_folder)

        if self._json_intervals_folder:
            self._move_json_files_to_final_dir(self._tempdir_intervals, self._json_intervals_folder)

    def _rm_tempdirs(self):
        # Remove temp folders
        shutil.rmtree(self._tempdir_main, ignore_errors=True)
        if self._tempdir_intervals:
            shutil.rmtree(self._tempdir_intervals, ignore_errors=True)
