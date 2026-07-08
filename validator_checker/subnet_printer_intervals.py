# standard imports
from rich.console import Console
from rich.text import Text

# Local imports
from .constants import (
    UPDATED_ERROR_THRESHOLD,
    UPDATED_WARNING_THRESHOLD,
    VTRUST_ERROR_THRESHOLD,
    VTRUST_WARNING_THRESHOLD,
    GREEN,
    RED,
    YELLOW,
    TAO,
)


class RichPrinter:
    def __init__(self, netuids, validator_data):
        self._console = Console()

        self._netuids = netuids
        self._validator_data = validator_data

        self._print_data()

    @staticmethod
    def _get_int_value(value):
        if value is None:
            return "---"
        return str(value)

    @classmethod
    def get_style(cls, status):
        if status == 2:
            return f"color({RED})"
        elif status == 1:
                return f"color({YELLOW})"
        else:
            return f"color({GREEN})"
    
    def _get_blocks_status(self, blocks):
        if blocks is None:
            return 2
        if  blocks > UPDATED_ERROR_THRESHOLD:
            return 2
        if blocks > UPDATED_WARNING_THRESHOLD:
            return 1
        return 0

    def _get_vtrust_status(self, vtrust, avg_vtrust):
        if avg_vtrust is None:
            return 1
        if (avg_vtrust - vtrust) > VTRUST_ERROR_THRESHOLD:
            return 2
        if (avg_vtrust - vtrust) > VTRUST_WARNING_THRESHOLD:
            return 1
        return 0

    def _print_data(self):
        text = Text()

        for netuid in self._netuids:
            text.append("\n")
            if netuid not in self._validator_data:
                text.append(
                    f"\nFailed to obtain data for subnet {netuid}",
                    style=self.get_style(2)
                )
                text.append("\n")
                continue

            subnet_data = self._validator_data[netuid]

            if (
                not subnet_data.mech_block_data
                or not any (mech_block_data.blocks for mech_block_data in subnet_data.mech_block_data)
            ):
                text.append(
                    f"\nRizzo validator not running on subnet {netuid}",
                    style=self.get_style(2)
                )
                text.append("\n")
                continue

            text.append(f"\nSubnet {netuid} ({subnet_data.subnet_emission:.2f}% "
                        f"- {subnet_data.subnet_alpha_price:.4f}{TAO}):")

            for mech_block_data in subnet_data.mech_block_data:
                if len(subnet_data.mech_block_data) > 1:
                    text.append(f"\nMech {mech_block_data.mechid} ({mech_block_data.mech_emission}%):")

                interval_blocks = []
                interval_vtrusts = []
                for subnet_block in mech_block_data.block_data:
                    blocks = subnet_block.rizzo_updated
                    blocks_status = self._get_blocks_status(blocks)
                    blocks = self._get_int_value(blocks)

                    vtrust = subnet_block.rizzo_vtrust
                    avg_vtrust = subnet_block.avg_vtrust
                    vtrust_status = self._get_vtrust_status(vtrust, avg_vtrust)
                    vtrust = f"{vtrust:.3f}"
            
                    max_chars = max(len(blocks), len(vtrust))
                    interval_blocks.append((f"{blocks:{max_chars}}", blocks_status))
                    interval_vtrusts.append((f"{vtrust:{max_chars}}", vtrust_status))

                text.append("\nUpdated Blocks:")
                for blocks, blocks_status in reversed(interval_blocks):
                    text.append(f"  {blocks}", style=self.get_style(blocks_status))
                
                text.append("\nVtrust Values: ")
                for vtrust, vtrust_status in reversed(interval_vtrusts):
                    text.append(f"  {vtrust}", style=self.get_style(vtrust_status))

                text.append("\n")
        
        self._console.print(text)
