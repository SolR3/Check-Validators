# standard imports
from dataclasses import dataclass, asdict
import json
import os
import requests
import tempfile
import time
import random

# bittensor import
import bittensor

# Local imports
from json_writer_base import JsonWriterBase,   LoopRunnerBase
from constants import (
    SUBNET_PRICE_FILE_NAME,
    TAOSTATS_HEADERS,
)
import utils


@dataclass
class SubnetPriceData:
    netuid: int
    tao_price_usd: float | None
    subnet_price_tao: float | None
    subnet_price_usd: float | None


class LoopRunnerPrice(LoopRunnerBase):
    def _makedirs(self):
        os.makedirs(self._options.json_folder, exist_ok=True)


class JsonWriterPrice(JsonWriterBase):
    def __init__(self, options):
        self._json_folder = options.json_folder
        self._sleep_time = options.seconds_between_queries

        super().__init__(options)

    def _create_tmp(self):
        # Make tmpdir for writing json files.
        self._tempdir = tempfile.mkdtemp(prefix="write_price_data_")

    def _write_json_files_to_tmp(self):
        bittensor.logging.info("Gathering subnet price data.")
        start_time = time.time()

        netuid_range = f"{self._netuids[0]}-{self._netuids[-1]}"
        json_file_name = utils.get_json_file_name(SUBNET_PRICE_FILE_NAME, netuid_range)
        json_file = os.path.join(self._tempdir, json_file_name)

        subnet_data = self._gather_subnet_data()
        data_dict = {
            netuid: asdict(subnet_data[netuid])
            for netuid in subnet_data
        }

        bittensor.logging.info(f"Writing data to file: {json_file}")
        with open(json_file, "w") as fd:
            json.dump(data_dict, fd, indent=4)

        total_time = round(time.time() - start_time)
        bittensor.logging.info(
            f"Subnet data gathering took {utils.get_formatted_time(total_time)}."
        )

    def _mv_tmp_to_final(self):
        # Move files over to final location and write timestamp.
        self._move_json_files_to_final_dir(self._tempdir, self._json_folder)
        self._write_timestamp(self._json_folder, SUBNET_PRICE_FILE_NAME, write_actual_time=False)

    def _gather_subnet_data(self):
        subnet_data = {}

        bittensor.logging.info("Gathering tao price")
        tao_price_usd = self._get_price_from_url()

        for netuid in self._netuids:
            bittensor.logging.info(f"Gathering subnet price for netuid {netuid}")

            try:
                subnet_price_tao = self._get_price_from_url(netuid)
            except Exception as e:
                bittensor.logging.error(f"Exception while fetching subnet {netuid}: {e}")
                subnet_price_tao = None

            if subnet_price_tao is None or tao_price_usd is None:
                subnet_price_usd = None
            else:
                subnet_price_usd = subnet_price_tao * tao_price_usd

            subnet_data[netuid] = SubnetPriceData(
                netuid=netuid,
                tao_price_usd=tao_price_usd,
                subnet_price_tao=subnet_price_tao,
                subnet_price_usd=subnet_price_usd,
            )

        return subnet_data

    # Courtesy of gregbeard, thanks Greg!
    def _get_price_from_url(self, netuid=None):
        if netuid is None:
            url = "https://api.taostats.io/api/price/latest/v1?asset=tao"
        else:
            url = f"https://api.taostats.io/api/dtao/pool/latest/v1?netuid={netuid}"

        response = self._query_url(url)
        if response.status_code != 200:
            bittensor.logging.error(f"Failed to obtain data from url: {url} ({response.reason})")
            return None

        data = response.json()
        price = data.get("data", [{}])[0].get("price")

        if price is None:
            bittensor.logging.error(f"No price data found on url: {url}")
            return None

        return float(price)

    def _query_url(self, url):
        num_attempts = 4

        for attempt in range(1, num_attempts + 1):
            wait = self._sleep_time + random.uniform(0, 5)
            bittensor.logging.info(f"Sleeping for {wait:.1f} seconds before attempt {attempt}.")
            time.sleep(wait)

            response = requests.get(url, headers=TAOSTATS_HEADERS, timeout=10)
            if response.status_code != 429:
                return response

            bittensor.logging.error(f"Attempt {attempt} failed due to rate limiting on url {url}")
            retry_wait = wait * attempt
            bittensor.logging.error(f"Sleeping for {retry_wait:.1f} seconds after failed attempt.")
            time.sleep(retry_wait)  # exponential backoff before next try

        return response
