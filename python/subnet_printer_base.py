# Local imports
from subnet_constants import (
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
