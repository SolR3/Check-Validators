# standard imports
from rich.text import Text
from rich.table import Table
from rich.console import Console
import time

# Local imports
from constants import (
    VTRUST_ERROR_THRESHOLD,
    VTRUST_WARNING_THRESHOLD,
    UPDATED_ERROR_THRESHOLD,
    UPDATED_WARNING_THRESHOLD,
)


class RichPrinterBase:
    _blue = "12"
    _red = "9"
    _green = "10"
    _yellow = "11"
    _white = "15"
    _tab = "    "
    _tao = "\u03c4"

    def __init__(self):
        self._console = Console()

    @classmethod
    def _get_style(cls, status):
        if status == 2:
            return f"color({cls._red})"
        if status == 1:
                return f"color({cls._yellow})"
        if status == 0:
            return f"color({cls._green})"
        if status == -1:
            return f"color({cls._white})"
        if status == -2:
            return f"color({cls._blue})"
        return ""

    @staticmethod
    def _get_float_value(value, dashes_if_none):
        if value is None:
            return "---" if dashes_if_none else ""
        return f"{value:.3f}"

    @staticmethod
    def _get_int_value(value, dashes_if_none):
        if value is None:
            return "---" if dashes_if_none else ""
        return str(value)

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
    def _get_chk_vtrust_status(vtrust, avg_vtrust):
        if avg_vtrust is None:
            return 1
        if vtrust is None:
            return 2
        if vtrust < 0.9:
            return 2
        if vtrust < 0.95:
            return 1
        return 0
    
    @staticmethod
    def _get_vtrust_gap_status(vtrust_gap):
        if vtrust_gap is None:
            return 0
        if vtrust_gap > 0.2:
            return 2
        if vtrust_gap > 0.05:
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


class TablePrinterBase(RichPrinterBase):
    reverse_sort = True
    _table_title_suffix = None  # This is defined in subclassess

    def __init__(self, vali_name):
        super().__init__()

        self._extra_printout = []
        self._vali_name = vali_name or "Rizzo"

        table_title = f"{self._vali_name} {self._table_title_suffix} - {time.ctime()}"
        self._table = Table(title=table_title)

        for column_header in self._get_column_headers():
            self._table.add_column(column_header, justify="left", no_wrap=True)

    def _get_column_headers(self, *args, **kwargs):
        raise NotImplementedError

    def update_printout(self, validator_data):
        row_columns = self._get_row(validator_data)
        self._table.add_row(*row_columns)

    def _get_row(self, *args, **kwargs):
        raise NotImplementedError

    def add_extra_printout(self, missing_data):
        if missing_data:
            self._extra_printout.append(
                Text(
                    "\nFailed to obtain data from the following subnets."
                    "\n(Try running these separately)"
                    "\n===================="
                    f"\n{self._tab}{', '.join(sorted(missing_data))}",
                    style=self._get_style(2)
                )
            )

    def print_everything(self):
        self._console.print(self._table)

        for text in self._extra_printout:
            self._console.print(text)
