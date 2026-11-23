# standard imports
from rich.console import Console
from rich.text import Text
import sys

# Local imports
from .constants import COLDKEYS


class RichPrinter:
    def __init__(
            self, validator_data, mechid, diff,
            print_weights, target_uids, threshold,
    ):
        self._console = Console()
        self._text = Text()

        # Should only ever be one netuid
        self._validator_data = list(validator_data.values())[0]
        self._mechid = mechid
        self._diff = diff
        self._print_weights = print_weights
        self._target_uids = target_uids
        self._threshold = threshold

        self._print_data()

    @staticmethod
    def _get_color(vali_type):
        return {
            0: "bright_green",  # Rizzo
            1: "bright_cyan",   # Owner
            2: "bright_blue",   # Legit Vali
            3: "bright_red",    # Weight Copier
            4: "default",       # Unknown Vali
        }.get(vali_type)

    def _print_data(self):
        if self._diff:
            self._get_weight_diffs_printout()
        else:
            self._get_weights_printout()
        self._console.print(self._text)

    def _get_weights_printout(self):
        owner_uid = self._validator_data.subnet_owner.uid
        owner_hotkey = self._validator_data.subnet_owner.hotkey
        owner_coldkey = self._validator_data.subnet_owner.coldkey

        self._text.append("\nOwner:\n==========\n")
        self._text.append(f"uid: {owner_uid}\n")
        self._text.append(f"hotkey: {owner_hotkey}\n")
        self._text.append(f"coldkey: {owner_coldkey}\n\n\n")
        self._text.append("Weights:\n==========\n")

        for validator in self._validator_data.validator_weights:
            uid = validator.uid
            hotkey = validator.hotkey
            coldkey = validator.coldkey
            name = validator.vali_name
            color = self._get_color(validator.vali_type)

            vtrust =  validator.vtrust
            updated = validator.updated[self._mechid]
            weights = self._get_weights(validator)
            num_weights = len(weights)

            if name:
                self._text.append(f"{name}:\n", style=color)
            self._text.append(f"uid: {uid}\n")
            self._text.append(f"hotkey: {hotkey}\n")
            self._text.append(f"coldkey: {coldkey}\n")
            self._text.append(f"Weights: {num_weights}  vTrust: {vtrust:.3f}  Updated: {updated}\n")
            if self._print_weights:
                self._text.append(str(weights) + "\n")
            self._text.append("\n")

    def _get_weights(self, validator):
        def filter_weight(i, w):
            if not w or w < self._threshold:
                return False
            if self._target_uids and i not in self._target_uids:
                return False
            return True

        weights = [(i, w) for i, w in validator.weights[self._mechid].items() if filter_weight(i, w)]
        weights.sort(key=lambda w: w[0])

        return weights

    def _get_weight_diffs_printout(self):

        def get_validator(uid):
            for validator in self._validator_data.validator_weights:
                if validator.uid == uid:
                    return validator

        uid_a, uid_b = self._get_diff_uids()

        validator_a = get_validator(uid_a)
        validator_b = get_validator(uid_b)
        vtrust_a = validator_a.vtrust
        vtrust_b = validator_b.vtrust
        updated_a = validator_a.updated[self._mechid]
        updated_b = validator_b.updated[self._mechid]
        hotkey_a = validator_a.hotkey
        hotkey_b = validator_b.hotkey

        self._text.append("\nHotkeys:\n=========\n")
        self._text.append(f"{uid_a:<3} - {hotkey_a} (vT: {vtrust_a:.3f}  U: {updated_a})\n")
        self._text.append(f"{uid_b:<3} - {hotkey_b} (vT: {vtrust_b:.3f}  U: {updated_b})\n")
        self._text.append("\n")

        weight_diffs = self._get_weight_diffs(validator_a, validator_b)

        self._text.append("Weight Diffs:\n==============\n")
        self._text.append(f"{len(weight_diffs)} differences\n")
        self._text.append("\n")
        if self._print_weights:
            for uid, weight_diff, weight_a, weight_b in weight_diffs:
                self._text.append(f"{uid}:\n")
                self._text.append(f"{weight_diff}  ({weight_a} - {weight_b})\n")
                self._text.append("\n")

    def _get_diff_uids(self):
        uids = []

        for diff_val in self._diff:
            try:
                uid = int(diff_val)
            except ValueError:
                for validator in self._validator_data.validator_weights:
                    if validator.hotkey == diff_val:
                        uid = validator.uid
                        break
                    elif COLDKEYS.get(diff_val.replace(".", "_")) == validator.coldkey:
                        uid = validator.uid
                        break

            if uid is None:
                Console().print(Text(
                    f"ERROR: Could not find uid for {diff_val}.",
                    style="color(9)"))
                sys.exit(1)

            uids.append(uid)

        return uids

    def _get_weight_diffs(self, validator_a, validator_b):
        weights_a = validator_a.weights[self._mechid]
        weights_b = validator_b.weights[self._mechid]
        weight_diffs = []

        for target_uid in sorted(set(weights_a) | set(weights_b)):
            if self._target_uids and target_uid not in self._target_uids:
                continue

            weight_a = weights_a.get(target_uid, 0.0)
            weight_b = weights_b.get(target_uid, 0.0)
            diff = weight_a - weight_b
            if not diff or abs(diff) < self._threshold:
                continue

            weight_diffs.append((target_uid, diff, weight_a, weight_b))

        return weight_diffs
