# standard imports
import json
import os
import time

# bittensor import
import bittensor

# Import local constants
from constants import (
    LOCAL_TIMEZONE,
    TIMESTAMP_FILE_NAME,
)


def get_formatted_time(total_time):
    # Get hours
    h = total_time/3600
    hours = int(h)

    # Get minutes
    remainder = round((h - hours)*3600)
    m = remainder/60
    minutes = int(m)

    # Get seconds
    seconds = round((m - minutes)*60)

    # Get formatted time
    formatted_time = [f"{hours} hours"] if hours else []
    if minutes:
        formatted_time.append(f"{minutes} minutes")
    if seconds or not formatted_time:
        formatted_time.append(f"{seconds} seconds")
    formatted_time = ", ".join(formatted_time)

    return formatted_time


def get_all_subnets(network):
    with bittensor.Subtensor(network=network) as subtensor:
        try:
            all_subnets = subtensor.get_all_subnets_netuid()
        except AttributeError:
            all_subnets = subtensor.get_subnets()

        return all_subnets[1:]


def get_subtensor_network(name):
    if name:
        return name if ":" in name else f"ws://subtensor-{name}.rizzo.network:9944"
    return "finney"


def write_timestamp(
        json_folder, data_file_name,
        write_display_time=True, write_actual_time=True
):
    os.environ["TZ"] = LOCAL_TIMEZONE
    time.tzset()

    max_file_time = 0
    json_base, json_ext = os.path.splitext(data_file_name)
    for _file in os.listdir(json_folder):
        file_base, file_ext = os.path.splitext(_file)
        if not file_base.startswith(json_base) or file_ext != json_ext:
            continue

        json_file = os.path.join(json_folder, _file)
        file_time = os.path.getmtime(json_file)
        if file_time > max_file_time:
            max_file_time = file_time
    
    display_time = time.ctime(max_file_time)
    actual_time = int(max_file_time)

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
