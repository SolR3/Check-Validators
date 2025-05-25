# standard imports
from rich.text import Text
from rich.table import Table
from rich.console import Console

# Local imports
from subnet_printer_base import RichPrinterBase


class SubnetDataPrinter:
    def __init__(
            self, subnet_data_class,
            netuids, pending, sort_subnets, vali_name,
            *subnet_data_args
        ):
        self._netuids = netuids
        self._pending = pending
        self._sort_subnets = sort_subnets
        self._vali_name = vali_name
        self._validator_data = subnet_data_class(*subnet_data_args).validator_data

    def print_validator_data(self):
        if self._pending:
            printer = PendingCHKTablePrinter(self._vali_name)
            child_hotkey_attr = "pending_child_hotkey_data"
        else:
            printer = CHKTablePrinter(self._vali_name)
            child_hotkey_attr = "child_hotkey_data"

        def sort_key(netuid):
            sort_key = self._validator_data[netuid].subnet_emission
            if printer.reverse_sort:
                sort_key *= -1
            return sort_key

        missing_data = []
        no_chk_subntets = []

        # Loop through all subnets and print out their CHK data.
        if self._netuids:
            netuids = (sorted(self._netuids, key=sort_key)
                       if self._sort_subnets else self._netuids)
        else:
            netuids = (sorted(self._validator_data, key=sort_key)
                       if self._sort_subnets else self._validator_data.keys())

        for netuid in netuids:
            if netuid not in self._validator_data:
                missing_data.append(str(netuid))
                continue

            validator_data = self._validator_data[netuid]

            if not getattr(validator_data, child_hotkey_attr):
                if self._netuids:
                    no_chk_subntets.append(str(netuid))
                continue

            printer.update_printout(validator_data)

        # Print extra stuff
        printer.add_extra_printout(missing_data, no_chk_subntets)
        
        # Print everything
        printer.print_everything()


class RichPrinter(RichPrinterBase):
    def __init__(self):
        self._console = Console()
        self._extra_printout = []

    def add_extra_printout(self, missing_data, no_chk_subntets):
        if missing_data:
            self._extra_printout.append(
                 Text("\nFailed to obtain data from the following subnets."
                      "\n(Try running these separately)"
                      "\n===================="
                     f"\n{self._tab}{', '.join(sorted(missing_data))}",
                      style=self._get_style(2)))

        if no_chk_subntets:
            self._extra_printout.append(
                 Text("\nThe following subnets do not have child hotkeys."
                      "\n===================="
                     f"\n{self._tab}{', '.join(sorted(no_chk_subntets))}",
                      style=self._get_style(1)))

    def print_everything(self):
        for text in self._extra_printout:
            self._console.print(text)


class TablePrinter(RichPrinter):
    _table_title_suffix = None  # This is defined in subclassess
    _child_hotkey_attr = None  # This is defined in subclassess
    reverse_sort = True

    def __init__(self, vali_name):
        super().__init__()

        if vali_name is None:
            vali_name = "Rizzo"

        table_title = f"{vali_name} " + self._table_title_suffix
        self._table = Table(title=table_title)
        for column_header in self._get_column_headers():
            self._table.add_column(column_header, justify="left", no_wrap=True)

    def _get_column_headers(self):
        column_headers = [
            "Subnet",
            "Subnet E",
            "CHK %",
            "Take %",
            "vTrust",
            "Updated",
            "Hotkey"
        ]

        return column_headers

    def update_printout(self, validator_data):
        row_columns = self._get_row(validator_data)
        self._table.add_row(*row_columns)

    def _get_row(self, validator_data):
        row_status = 0
        chk_percents = []
        chk_hotkeys = []
        chk_takes = []
        chk_vtrusts = []
        chk_updateds = []
        epsilon = 1e-5
        for child_hotkey in getattr(validator_data, self._child_hotkey_attr):
            hotkey_vtrust_status = self._get_vtrust_status(
                child_hotkey.vtrust, validator_data.avg_vtrust
            )
            hotkey_updated_status = self._get_updated_status(
                child_hotkey.updated, validator_data.avg_updated
            )
            hotkey_take_status = (
                2 if child_hotkey.take + epsilon >= 0.09
                else (
                    1 if child_hotkey.take - epsilon > 0.0
                    else 0
                )
            )
            row_status = max(
                row_status,
                hotkey_vtrust_status,
                hotkey_updated_status,
                hotkey_take_status
            )

            hotkey_percent = int(round(child_hotkey.fraction * 100))
            chk_percents.extend([f"{hotkey_percent}%", "\n"])

            hotkey_take = int(round(child_hotkey.take * 100))
            chk_takes.extend(
                [(f"{hotkey_take}%", self._get_style(hotkey_take_status)), "\n"]
            )

            chk_vtrusts.extend(
                [(f"{child_hotkey.vtrust:.3f}", self._get_style(hotkey_vtrust_status)), "\n"]
            )

            chk_updateds.extend(
                [(str(child_hotkey.updated), self._get_style(hotkey_updated_status)), "\n"]
            )

            chk_hotkeys.extend([child_hotkey.hotkey, "\n"])

        chk_percents.pop()
        chk_takes.pop()
        chk_vtrusts.pop()
        chk_updateds.pop()
        chk_hotkeys.pop()

        row_columns = [
            Text(
                str(validator_data.netuid),
                style=self._get_style(row_status)
            ),
            Text(f"{validator_data.subnet_emission:.2f}%"),
            Text.assemble(*chk_percents),
            Text.assemble(*chk_takes),
            Text.assemble(*chk_vtrusts),
            Text.assemble(*chk_updateds),
            Text.assemble(*chk_hotkeys),
        ]
        
        return row_columns

    def print_everything(self):
        self._console.print(self._table)
        super().print_everything()


class CHKTablePrinter(TablePrinter):
    _table_title_suffix = "CHK"
    _child_hotkey_attr = "child_hotkey_data"


class PendingCHKTablePrinter(TablePrinter):
    _table_title_suffix = "Pending CHK"
    _child_hotkey_attr = "pending_child_hotkey_data"

    def _get_column_headers(self):
        column_headers = super()._get_column_headers()
        column_headers.insert(-1, "Pending Time")

        return column_headers

    def _get_row(self, validator_data):
        row_columns = super()._get_row(validator_data)

        def format_time(s):
            h = s / 3600
            hours = int(h)
            minutes = round((h - hours) * 60)
            time_tuple = [f"{hours}h"] if hours else []
            if minutes or not hours:
                time_tuple.append(f"{minutes}m")
            return ",".join(time_tuple)

        chk_pending_time = format_time(validator_data.chk_pending_time)
        row_columns.insert(-1, Text(chk_pending_time))

        return row_columns
