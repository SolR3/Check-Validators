# standard imports
import os
import random


# Import local constants
from constants import LOCAL_LITE_SUBTENSORS


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


def _create_get_lite_subtensor_network():
    # Randomize local subtensor.
    random.seed()
    local_subtensor_index = random.randint(0, len(LOCAL_LITE_SUBTENSORS) - 1)

    def get_network(name=None):

        def get_network_from_name(name):
            return name if ":" in name else f"ws://subtensor-{name}.rizzo.network:9944"
        
        if name is False:
            return "finney"

        if name is None:
            nonlocal local_subtensor_index
            local_subtensor_index = (local_subtensor_index + 1) % len(LOCAL_LITE_SUBTENSORS)
            name = LOCAL_LITE_SUBTENSORS[local_subtensor_index]

        return get_network_from_name(name)
    
    return get_network

get_lite_subtensor_network = _create_get_lite_subtensor_network()


def get_json_file_name(json_file_name, netuid):
    json_base, json_ext = os.path.splitext(json_file_name)
    return f"{json_base}.{netuid}{json_ext}"
