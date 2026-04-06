# standard imports
import multiprocessing
import os
import json
import shutil
import time

# bittensor import
import bittensor

# Local imports
from constants import (
    LOCAL_TIMEZONE,
    TIMESTAMP_FILE_NAME,
)
import utils


mp_queue = multiprocessing.Queue()


class SubtensorConnectionError(Exception):
    pass


class LoopRunnerBase:
    def __init__(self, run_func, options):
        self._run_func = run_func
        self._options = options

        bittensor.logging.enable_info()

        self._makedirs()
        self._run_write_json_loop()

    def _makedirs(self):
        raise NotImplementedError

    def _run_write_json_loop(self):
        while True:
            start_time = time.time()
            self._options.lite_network = utils.get_lite_subtensor_network(self._options.local_lite_subtensor)

            args = [self._options]
            try:
                with multiprocessing.Pool(processes=1) as pool:
                    pool.apply(self._run_func, args)
            except SubtensorConnectionError:
                if self._options.local_lite_subtensor is None:
                    bittensor.logging.error("Rotating subtensors and trying again.")
                    time.sleep(1)
                    continue
            finally:
                while not mp_queue.empty():
                    tempdirs = mp_queue.get()
                    for tempdir in tempdirs:
                        shutil.rmtree(tempdir, ignore_errors=True)

            # Only gather the data once.
            if not self._options.interval_seconds:
                break

            total_seconds = round(time.time() - start_time)
            wait_seconds = self._options.interval_seconds - total_seconds
            if wait_seconds > 0:
                wait_time_formatted = utils.get_formatted_time(wait_seconds)
                bittensor.logging.info(f"Waiting {wait_time_formatted}.")
                time.sleep(wait_seconds)
            else:
                bittensor.logging.warning(
                    f"Processing took {total_seconds} seconds which is longer "
                    f"than {self._options.interval_seconds} seconds. Not waiting."
                )


class JsonWriterBase:
    def __init__(self, options):
            self._lite_network = options.lite_network
            self._run()

    def _run(self):
        # Get all Subnets.
        bittensor.logging.info(f"Connecting to network: {self._lite_network}")
        try:
            self._netuids = utils.get_all_subnets(self._lite_network)
        except Exception as err:
            bittensor.logging.error(f"Subtensor connection failed on '{self._lite_network}'")
            bittensor.logging.error(f"{type(err).__name__}: {err}")
            raise SubtensorConnectionError

        try:
            self._mk_tempdirs()
            self._write_json_files_to_tmp()
            self._mv_tmp_to_final()
        finally:
            self._rm_tempdirs()

    def _mk_tempdirs(self):
        raise NotImplementedError

    def _write_json_files_to_tmp(self):
        raise NotImplementedError

    def _mv_tmp_to_final(self):
         raise NotImplementedError

    def _rm_tempdirs(self):
        raise NotImplementedError

    @staticmethod
    def _move_json_files_to_final_dir(temp_dir, final_dir):
        # Remove old files from final folder
        for file_name in os.listdir(final_dir):
            file_path = os.path.join(final_dir, file_name)
            if (
                not os.path.isfile(file_path)
                or os.path.splitext(file_path)[1] != ".json"
            ):
                continue
            bittensor.logging.info(f"Removing {file_path}")
            os.unlink(file_path)

        # Copy files from temp folder to final folder
        for file_name in os.listdir(temp_dir):
            src_file_path = os.path.join(temp_dir, file_name)
            dest_file_path = os.path.join(final_dir, file_name)
            bittensor.logging.info(f"Moving {src_file_path} to {dest_file_path}")
            os.rename(src_file_path, dest_file_path)

    @staticmethod
    def _write_timestamp(
            json_folder, data_file_name,
            write_display_time=True, write_actual_time=True
    ):
        os.environ["TZ"] = LOCAL_TIMEZONE
        time.tzset()

        min_file_time = 0
        json_base, json_ext = os.path.splitext(data_file_name)
        for _file in os.listdir(json_folder):
            file_base, file_ext = os.path.splitext(_file)
            if not file_base.startswith(json_base) or file_ext != json_ext:
                continue

            json_file = os.path.join(json_folder, _file)
            file_time = os.path.getmtime(json_file)
            if min_file_time == 0 or file_time < min_file_time:
                min_file_time = file_time
        
        display_time = time.ctime(min_file_time)
        actual_time = int(min_file_time)

        if write_display_time and write_actual_time:
            timestamp = {
                "display_time": display_time,
                "actual_time": actual_time,
            }
        elif write_display_time:
            timestamp = display_time
        elif write_actual_time:
            timestamp = actual_time
        else:
            timestamp = None

        timestamp_file = os.path.join(json_folder, TIMESTAMP_FILE_NAME)
        bittensor.logging.info(f"Writing timestamp file: {timestamp_file}")
        with open(timestamp_file, "w") as fp:
            json.dump(timestamp, fp)
