# bittensor import
import bittensor


def format_time(total_time):
    m = total_time/60
    minutes = int(m)
    seconds = round((m - minutes)*60)

    runtime_text = f"{minutes} minutes, " if minutes else ""
    runtime_text += f"{seconds} seconds"

    return runtime_text


def get_all_subnets(network):
    with bittensor.Subtensor(network=network) as subtensor:
        try:
            all_subnets = subtensor.get_all_subnets_netuid()
        except AttributeError:
            all_subnets = subtensor.get_subnets()

        return all_subnets[1:]
