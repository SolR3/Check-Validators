# standard imports
from rich.text import Text

# Local imports
from .constants import (
    COLDKEYS,
    EPSILON,
    TAO,
)
from .subnet_printer_base import TablePrinterBase


class SubnetDataPrinter:
    def __init__(
            self, validator_data, netuids, chk_only, missing_chk,
            sort_subnets, print_total_emission, coldkey,
        ):
        self._netuids = netuids
        self._chk_only = chk_only
        self._missing_chk = missing_chk
        self._sort_subnets = sort_subnets
        self._print_total_emission = print_total_emission
        self._validator_data = validator_data
        self._vali_name = self._get_vali_name(coldkey)

    def _get_vali_name(self, coldkey):
        if not coldkey:
            return "Rizzo"

        for vali_name in COLDKEYS:
            if coldkey.lower().replace(".", "_") == vali_name.lower():
                return coldkey.capitalize()

        return coldkey[:6] + "..."

    def print_validator_data(self):
        printer = TablePrinter(self._vali_name)

        def sort_key(netuid):
            sort_key = self._validator_data[netuid].subnet_emission
            if printer.reverse_sort:
                sort_key *= -1
            return sort_key

        total_emission = 0.0
        missing_data = []

        # Loop through all subnets and print out
        # their vtrust and updated data.
        if self._netuids:
            netuids = (
                sorted(self._netuids, key=sort_key)
                if self._sort_subnets else self._netuids
            )
        else:
            netuids = (
                sorted(self._validator_data, key=sort_key)
                if self._sort_subnets else self._validator_data.keys()
            )

        for netuid in netuids:
            if netuid not in self._validator_data:
                missing_data.append(str(netuid))
                continue

            validator_data = self._validator_data[netuid]

            if self._chk_only and not validator_data.child_hotkey_data:
                continue

            if self._missing_chk and validator_data.missing_chk <= EPSILON:
                continue

            if validator_data.rizzo_emission is not None:
                total_emission += validator_data.rizzo_emission

            printer.update_printout(validator_data)

        # Print extra stuff
        printer.add_extra_printout(
            missing_data,
            total_emission if self._print_total_emission else None
        )
        
        # Print everything
        printer.print_everything()


class TablePrinter(TablePrinterBase):
    _table_title_suffix = "Validators"

    def _get_column_headers(self):
        column_headers = [
            "Subnet",
            "Emission",
            "Alpha",
            "# Valis",
            "CHK vT",
            "CHK ?",
            f"{self._vali_name} vT",
            "Rt21 vT Gap",
            "Tao.com vT Gap",
            "Yuma vT Gap",
            "Max vT",
            "Avg vT",
            "Min vT",
            "CHK U",
            "Mech",
            f"{self._vali_name} U",
            "Min U",
            "Avg U",
            "Max U",
        ]
        return column_headers

    def _get_row(self, validator_data):
        chk_updateds = []
        rizzo_updateds = []
        min_updateds = []
        avg_updateds = []
        max_updateds = []
        mechs = []

        num_mechs = len(validator_data.subnet_mechs)

        chk_updated_list = self._get_updated_list(validator_data.chk_updated, num_mechs)
        rizzo_updated_list = self._get_updated_list(validator_data.rizzo_updated, num_mechs)
        min_updated_list = self._get_updated_list(validator_data.min_updated, num_mechs)
        avg_updated_list = self._get_updated_list(validator_data.avg_updated, num_mechs)
        max_updated_list = self._get_updated_list(validator_data.max_updated, num_mechs)

        rizzo_vtrust_status = self._get_vtrust_status(
            validator_data.rizzo_vtrust, validator_data.avg_vtrust
        )
        rizzo_updated_statuses = [
            self._get_updated_status(rizzo_updated_list[i], avg_updated_list[i])
            for i in range(num_mechs)
        ]

        chk_vtrust_status = self._get_chk_vtrust_status(
            validator_data.chk_vtrust, validator_data.avg_vtrust
        )
        chk_updated_statuses = [
            self._get_updated_status(chk_updated_list[i], avg_updated_list[i])
            for i in range(num_mechs)
        ]

        missing_chk_status = (
            2 if validator_data.missing_chk > EPSILON
            else 0
        )

        rt21_vtrust_gap_status = self._get_vtrust_gap_status(
            validator_data.rt21_vtrust_gap
        )
        taocom_vtrust_gap_status = self._get_vtrust_gap_status(
            validator_data.taocom_vtrust_gap
        )
        yuma_vtrust_gap_status = self._get_vtrust_gap_status(
            validator_data.yuma_vtrust_gap
        )

        rizzo_vtrust_value = self._get_float_value(validator_data.rizzo_vtrust, True)
        chk_vtrust_value = self._get_float_value(validator_data.chk_vtrust, False)

        if chk_vtrust_value:
            chk_fraction_value = int(round(validator_data.chk_fraction * 100))
            chk_vtrust_value = f"{chk_vtrust_value} ({chk_fraction_value}%)"

        if validator_data.missing_chk > EPSILON:
            missing_chk_value = int(round(validator_data.missing_chk * 100))
            missing_chk_value = f"{missing_chk_value}%"
        else:
            missing_chk_value = ""

        rt21_vtrust_gap_value = self._get_float_value(
            validator_data.rt21_vtrust_gap, False
        )
        if rt21_vtrust_gap_value:
            rt21_vtrust_value = self._get_float_value(validator_data.rt21_vtrust, False)
            rt21_vtrust_gap_value = f"{rt21_vtrust_gap_value:>6} ({rt21_vtrust_value})"

        taocom_vtrust_gap_value = self._get_float_value(
            validator_data.taocom_vtrust_gap, False
        )
        if taocom_vtrust_gap_value:
            taocom_vtrust_value = self._get_float_value(validator_data.taocom_vtrust, False)
            taocom_vtrust_gap_value = f"{taocom_vtrust_gap_value:>6} ({taocom_vtrust_value})"

        yuma_vtrust_gap_value = self._get_float_value(
            validator_data.yuma_vtrust_gap, False
        )
        if yuma_vtrust_gap_value:
            yuma_vtrust_value = self._get_float_value(validator_data.yuma_vtrust, False)
            yuma_vtrust_gap_value = f"{yuma_vtrust_gap_value:>6} ({yuma_vtrust_value})"

        for mi in range(num_mechs):
            chk_updateds.extend(
                [(self._get_int_value(chk_updated_list[mi], False), self._get_style(chk_updated_statuses[mi])), "\n"]
            )
            rizzo_updateds.extend(
                [(self._get_int_value(rizzo_updated_list[mi], True), self._get_style(rizzo_updated_statuses[mi])), "\n"]
            )
            min_updateds.extend([self._get_int_value(min_updated_list[mi], True), "\n"])
            avg_updateds.extend([self._get_int_value(avg_updated_list[mi], True), "\n"])
            max_updateds.extend([self._get_int_value(max_updated_list[mi], True), "\n"])

            if num_mechs > 1:
                mechs.extend([f"{mi} ({validator_data.subnet_mechs[mi]}%)", "\n"])
            else:
                mechs.extend(["", "\n"])

        chk_updateds.pop()
        rizzo_updateds.pop()
        min_updateds.pop()
        avg_updateds.pop()
        max_updateds.pop()
        mechs.pop()

        row_columns = [
            Text(
                str(validator_data.netuid),
                style=self._get_style(
                    max(
                        rizzo_vtrust_status,
                        *rizzo_updated_statuses,
                        rt21_vtrust_gap_status,
                        taocom_vtrust_gap_status,
                        yuma_vtrust_gap_status,
                        missing_chk_status,
                        # chk_vtrust_status,
                        # *chk_updated_statuses,
                    )
                )
            ),
            Text(f"{validator_data.subnet_emission:.2f}%"),
            Text(f"{validator_data.subnet_alpha_price:.4f}{TAO}"),
            Text(
                f"{validator_data.num_valid_validators:>2}  "
                f"({validator_data.num_total_validators})"
            ),
            Text(
                chk_vtrust_value,
                style=self._get_style(chk_vtrust_status)
            ),
            Text(
                missing_chk_value,
                style=self._get_style(missing_chk_status)
            ),
            Text(
                rizzo_vtrust_value,
                style=self._get_style(rizzo_vtrust_status)
            ),
            Text(
                rt21_vtrust_gap_value,
                style=self._get_style(rt21_vtrust_gap_status)
            ),
            Text(
                taocom_vtrust_gap_value,
                style=self._get_style(taocom_vtrust_gap_status)
            ),
            Text(
                yuma_vtrust_gap_value,
                style=self._get_style(yuma_vtrust_gap_status)
            ),
            Text(self._get_float_value(validator_data.max_vtrust, True)),
            Text(self._get_float_value(validator_data.avg_vtrust, True)),
            Text(self._get_float_value(validator_data.min_vtrust, True)),
            Text.assemble(*chk_updateds),
            Text.assemble(*mechs),
            Text.assemble(*rizzo_updateds),
            Text.assemble(*min_updateds),
            Text.assemble(*avg_updateds),
            Text.assemble(*max_updateds),
        ]
    
        return row_columns

    def add_extra_printout(self, missing_data, total_emission):
        
        if total_emission is not None:
            self._extra_printout.append(
                Text(f"\nTotal Emission = {total_emission:.5f}")
            )

        super().add_extra_printout(missing_data)
