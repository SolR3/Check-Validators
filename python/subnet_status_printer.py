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
    def __init__(self, subnet_data_class, netuids, chk_only, *subnet_data_args):
        self._netuids = netuids
        self._chk_only = chk_only
        self._validator_data = subnet_data_class(*subnet_data_args).validator_data

    @staticmethod
    def _get_vtrust_status(vtrust, avg_vtrust):
        if avg_vtrust is None:
            return 1
        if vtrust is None:
            return 2
        if (avg_vtrust - vtrust) > VTRUST_ERROR_THRESHOLD:
            return 2
        if (avg_vtrust - vtrust) > VTRUST_WARNING_THRESHOLD:
            return 1
        return 0

    @staticmethod
    def _get_updated_status(updated, avg_updated):
        if avg_updated is None:
            return 1
        if updated is None:
            return 2
        if updated > UPDATED_ERROR_THRESHOLD:
            return 2
        if updated > UPDATED_WARNING_THRESHOLD:
            return 1
        return 0

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

            if self._chk_only and not validator_data.child_hotkey_data:
                continue

            if validator_data.rizzo_emission is not None:
                total_emission += validator_data.rizzo_emission

            rizzo_vtrust_status = self._get_vtrust_status(
                validator_data.rizzo_vtrust, validator_data.avg_vtrust
            )
            rizzo_updated_status = self._get_updated_status(
                validator_data.rizzo_updated, validator_data.avg_updated
            )

            chk_vtrust_status = self._get_vtrust_status(
                validator_data.chk_vtrust, validator_data.avg_vtrust
            )
            chk_updated_status = self._get_updated_status(
                validator_data.chk_updated, validator_data.avg_updated
            )

            printer.update_printout(
                validator_data,
                rizzo_vtrust_status, rizzo_updated_status,
                chk_vtrust_status, chk_updated_status,
            )

        # Print extra stuff
        printer.add_extra_printout(
            missing_data,
            total_emission if print_total_emission else None
        )
        
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
    
    def _get_float_value(self, value, dashes_if_none):
        if value is None:
            return "---" if dashes_if_none else ""
        return f"{value:.3f}"
        
    def _get_int_value(self, value, dashes_if_none):
        if value is None:
            return "---" if dashes_if_none else ""
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
            "Subnet", justify="left", no_wrap=True)
        self._table.add_column(
            "Subnet E", justify="left", no_wrap=True)
        # self._table.add_column(
        #     f"{vali_name} Rank", justify="left", no_wrap=True)
        # self._table.add_column(
        #     f"{vali_name} E", justify="left", no_wrap=True)
        self._table.add_column(
            "# Valis", justify="left", no_wrap=True)
        # self._table.add_column(
        #     "CHK %", justify="left", no_wrap=True)
        # self._table.add_column(
        #     f"{vali_name} %", justify="left", no_wrap=True)
        self._table.add_column(
            "CHK vT", justify="left", no_wrap=True)
        self._table.add_column(
            f"{vali_name} vT", justify="left", no_wrap=True)
        self._table.add_column(
            "Max vT", justify="left", no_wrap=True)
        self._table.add_column(
            "Avg vT", justify="left", no_wrap=True)
        self._table.add_column(
            "Min vT", justify="left", no_wrap=True)
        self._table.add_column(
            "CHK U", justify="left", no_wrap=True)
        self._table.add_column(
            f"{vali_name} U", justify="left", no_wrap=True)
        self._table.add_column(
            "Min U", justify="left", no_wrap=True)
        self._table.add_column(
            "Avg U", justify="left", no_wrap=True)
        self._table.add_column(
            "Max U", justify="left", no_wrap=True)

    def update_printout(
            self, validator_data,
            rizzo_vtrust_status, rizzo_updated_status,
            chk_vtrust_status, chk_updated_status
        ):
        # if validator_data.rizzo_stake_rank is None:
        #     rizzo_stake_rank = "---"
        # else:
        #     rizzo_stake_rank = (
        #         f"{validator_data.rizzo_stake_rank}/"
        #             f"{validator_data.num_validators}")

        rizzo_vtrust_value = self._get_float_value(validator_data.rizzo_vtrust, True)
        # rizzo_fraction_value = int(round((1.0 - validator_data.chk_fraction) * 100))
        # if rizzo_fraction_value == 100:
        #     rizzo_fraction_value = ""
        # else:
        #     rizzo_fraction_value = f"{rizzo_fraction_value}%"
        # if rizzo_fraction_value != 100:
        #     rizzo_vtrust_value = (
        #         f"{rizzo_vtrust_value:<2}  "
        #         f"({rizzo_fraction_value}%)"
        #     )
        
        chk_vtrust_value = self._get_float_value(validator_data.chk_vtrust, False)
        # chk_fraction_value = int(round(validator_data.chk_fraction * 100))
        # if chk_fraction_value == 0:
        #     chk_fraction_value = ""
        # else:
        #     chk_fraction_value = f"{chk_fraction_value}%"
        if chk_vtrust_value:
            chk_fraction_value = int(round(validator_data.chk_fraction * 100))
            chk_vtrust_value = f"{chk_vtrust_value} ({chk_fraction_value}%)"

        columns = [
            Text(f"{validator_data.netuid}",
                 style=self._get_style(
                     max(rizzo_vtrust_status, rizzo_updated_status))),
            Text(f"{validator_data.subnet_emission:.2f}%"),
            # Text(rizzo_stake_rank),
            # Text(self._get_float_value(validator_data.rizzo_emission, True)),
            Text(f"{validator_data.num_valid_validators:<2}  "
                 f"({validator_data.num_total_validators})"),
            # Text(f"{rizzo_fraction_value}"),
            # Text(chk_fraction_value),
            Text(chk_vtrust_value,
                 style=self._get_style(chk_vtrust_status)),
            Text(rizzo_vtrust_value,
                 style=self._get_style(rizzo_vtrust_status)),
            Text(self._get_float_value(validator_data.max_vtrust, True)),
            Text(self._get_float_value(validator_data.avg_vtrust, True)),
            Text(self._get_float_value(validator_data.min_vtrust, True)),
            Text(self._get_int_value(validator_data.chk_updated, False),
                 style=self._get_style(chk_updated_status)),
            Text(self._get_int_value(validator_data.rizzo_updated, True),
                 style=self._get_style(rizzo_updated_status)),
            Text(self._get_int_value(validator_data.min_updated, True)),
            Text(self._get_int_value(validator_data.avg_updated, True)),
            Text(self._get_int_value(validator_data.max_updated, True)),
        ]
        self._table.add_row(*columns)

    def print_everything(self):
        self._console.print(self._table)
        super().print_everything()
