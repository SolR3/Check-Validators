# standard imports
from rich.text import Text
from rich.table import Table
from rich.console import Console

from subnet_constants import (
    VTRUST_ERROR_THRESHOLD,
    VTRUST_WARNING_THRESHOLD,
    UPDATED_ERROR_THRESHOLD,
    UPDATED_WARNING_THRESHOLD,
)

class SubnetDataPrinter:
    def __init__(self, subnet_data_class, *args):
        self._netuids = None
        self._validator_data = subnet_data_class(*args).validator_data

    def set_netuids(self, netuids):
        self._netuids = netuids

    def print_validator_data(
            self, sort_subnets=True, print_total_emission=True, vali_name=None
        ):
        printer = TablePrinter(vali_name)

        def sort_key(netuid):
            sort_key = self._validator_data[netuid].subnet_emission
            if printer.reverse_sort:
                sort_key *= -1
            return sort_key

        total_emission = 0.0
        missing_data = []

        # Loop through all subnets and print out
        # their vtrust and updated data.
        if self._netuids is not None:
            netuids = (sorted(self._netuids, key=sort_key)
                       if sort_subnets else self._netuids)
        else:
            netuids = (sorted(self._validator_data, key=sort_key)
                       if sort_subnets else self._validator_data.keys())
        for netuid in netuids:
            if netuid not in self._validator_data:
                missing_data.append(str(netuid))
                continue

            validator_data = self._validator_data[netuid]

            if validator_data.rizzo_emission is not None:
                total_emission += validator_data.rizzo_emission

            if validator_data.rizzo_vtrust is None:
                vtrust_status = 2
            elif validator_data.avg_vtrust is None:
                vtrust_status = 1
            # Commenting this out for now. Sometimes the min vT is 0.9+ and
            # our vT is 0.9+ as well but just barely below the min so it shows
            # red when really it should be green.
            # elif validator_data.rizzo_vtrust < validator_data.min_vtrust:
            #     vtrust_status = 2
            elif (validator_data.avg_vtrust - validator_data.rizzo_vtrust) > VTRUST_ERROR_THRESHOLD:
                vtrust_status = 2
            elif (validator_data.avg_vtrust - validator_data.rizzo_vtrust) > VTRUST_WARNING_THRESHOLD:
                vtrust_status = 1
            else: 
                vtrust_status = 0

            if validator_data.rizzo_updated is None:
                updated_status = 2
            elif validator_data.avg_updated is None:
                updated_status = 1
            elif validator_data.rizzo_updated > UPDATED_ERROR_THRESHOLD:
                updated_status = 2
            elif validator_data.rizzo_updated > UPDATED_WARNING_THRESHOLD:
                updated_status = 1
            else:
                updated_status = 0

            printer.update_printout(
                validator_data, vtrust_status, updated_status)

        # Print extra stuff
        printer.add_extra_printout(
            missing_data,
            total_emission if print_total_emission else None)
        
        # Print everything
        printer.print_everything()


class RichPrinter:
    _red = "9"
    _green = "10"
    _yellow = "11"
    _tab = "    "

    def __init__(self):
        self._console = Console()
        self._extra_printout = []

    def _get_style(self, status):
        if status == 2:
            return f"color({self._red})"
        elif status == 1:
                return f"color({self._yellow})"
        else:
            return f"color({self._green})"
    
    def _get_float_value(self, value):
        if value is None:
            return "---"
        return f"{value:.5f}"
        
    def _get_int_value(self, value):
        if value is None:
            return "---"
        return str(value)
    
    def add_extra_printout(self, missing_data, total_emission):
        
        if total_emission is not None:
            self._extra_printout.append(
                Text(f"\nTotal Emission = {total_emission:.5f}"))

        if missing_data:
            self._extra_printout.append(
                 Text("\nFailed to obtain data from the following subnets."
                      "\n(Try running these separately)"
                      "\n===================="
                     f"\n{self._tab}{', '.join(sorted(missing_data))}",
                      style=self._get_style(2)))

    def print_everything(self):
        for text in self._extra_printout:
            self._console.print(text)


class TablePrinter(RichPrinter):
    reverse_sort = True

    def __init__(self, vali_name):
        super().__init__()

        if vali_name is None:
            vali_name = "Rizzo"

        self._table = Table(title=f"{vali_name} Validators")
        self._table.add_column(
            "Subnet", justify="center", no_wrap=True)
        self._table.add_column(
            "Subnet E", justify="center", no_wrap=True)
        # self._table.add_column(
        #     f"{vali_name} Rank", justify="center", no_wrap=True)
        # self._table.add_column(
        #     f"{vali_name} E", justify="center", no_wrap=True)
        self._table.add_column(
            "# Valis", justify="center", no_wrap=True)
        self._table.add_column(
            f"{vali_name} vT", justify="center", no_wrap=True)
        self._table.add_column(
            "Max vT", justify="center", no_wrap=True)
        self._table.add_column(
            "Avg vT", justify="center", no_wrap=True)
        self._table.add_column(
            "Min vT", justify="center", no_wrap=True)
        self._table.add_column(
            f"{vali_name} U", justify="center", no_wrap=True)
        self._table.add_column(
            "Min U", justify="center", no_wrap=True)
        self._table.add_column(
            "Avg U", justify="center", no_wrap=True)
        self._table.add_column(
            "Max U", justify="center", no_wrap=True)

    def update_printout(self, validator_data, vtrust_status, updated_status):
        # if validator_data.rizzo_stake_rank is None:
        #     rizzo_stake_rank = "---"
        # else:
        #     rizzo_stake_rank = (
        #         f"{validator_data.rizzo_stake_rank}/"
        #             f"{validator_data.num_validators}")

        columns = [
            Text(f"{validator_data.netuid}",
                 style=self._get_style(max(vtrust_status, updated_status))),
            Text(f"{validator_data.subnet_emission:.2f}%"),
            # Text(rizzo_stake_rank),
            # Text(self._get_float_value(validator_data.rizzo_emission)),
            Text(f"{validator_data.num_valid_validators:<2}  "
                 f"({validator_data.num_total_validators})"),
            Text(self._get_float_value(validator_data.rizzo_vtrust),
                 style=self._get_style(vtrust_status)),
            Text(self._get_float_value(validator_data.max_vtrust)),
            Text(self._get_float_value(validator_data.avg_vtrust)),
            Text(self._get_float_value(validator_data.min_vtrust)),
            Text(self._get_int_value(validator_data.rizzo_updated),
                 style=self._get_style(updated_status)),
            Text(self._get_int_value(validator_data.min_updated)),
            Text(self._get_int_value(validator_data.avg_updated)),
            Text(self._get_int_value(validator_data.max_updated)),
        ]
        self._table.add_row(*columns)

    def print_everything(self):
        self._console.print(self._table)
        super().print_everything()
