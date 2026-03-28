# bittensor import
import bittensor


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
