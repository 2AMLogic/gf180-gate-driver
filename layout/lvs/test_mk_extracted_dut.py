#!/usr/bin/env python3
"""Unit tests for ``mk_extracted_dut.py``'s merged-ground parasitic handling.

Stdlib-only, no ``klt``, no PDK, no ngspice: builds the DUT in-process from
the same committed ``klt extract --parasitics`` report the CI "Extracted
post-layout DUT netlists are in sync" step re-derives the committed netlist
from, so this runs on the PDK-free runner alongside
``layout/lvs/test_make_reference.py``.

What it pins is the one transform in this script whose *wrong* form still
produces a plausible-looking, simulatable netlist: since issue #132 the
extraction deck reports both drawn ground rails under one merged identity
(``GND_DRV|GND_LOGIC``, klayout-tools #1128), and that net's parasitic star
must be emitted with **each leg's hub rebound to that leg's own device's real
rail**. Two failure modes it guards against, both silent:

* **A shared hub** (any single node standing in for the merged identity) --
  known wrong per ``MERGED_GROUND_RAW``'s docstring: it puts the 6 V output
  stage's return current on the same node as the 3.3 V logic's, routing it
  through the testbench's inter-rail tie resistor instead of straight to the
  load's own return, and a full-PVT regression measured worse undershoot at
  nearly every corner as a result.
* **Skipping the star** (issue #184's original report) -- leaves both rails
  as ideal zero-ohm nodes, which is optimistic, not conservative, for the
  ground-bounce/undershoot checks the RC record exists to make.

Neither shows up as an error, a warning, or a convergence failure: both just
quietly change what the evidence means.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mk_extracted_dut as mk  # noqa: E402  (path set above)

REPORTS = Path(__file__).resolve().parent / "reports" / "gate_driver_core"

#: A pre-#166 (pre-XCCOMP) pair of committed reports, pinned deliberately
#: rather than tracked to whatever CI's `--check` step currently re-derives
#: the committed DUTs from (issue #201): every count this module's assertions
#: pin below (297 legs, 2877 R / 17 C, the 294/3 domain split, 16 "other"
#: ground-referenced capacitors) is a fact about the merged-ground star
#: transform on *MOS terminals*, and is unaffected by #166's XCCOMP MiM
#: stack. Re-pointing these constants at a post-#166 report would also pull
#: in T7's four series MiM device cards, which the "capacitors" fixture below
#: cannot yet distinguish from T5's per-net ground-star cards (both emit `C*`
#: cards) without the several assertions below being taught that
#: distinction -- left as a real, separate refactor rather than folded into
#: #201's netlist-regeneration scope.
RC_REPORT = REPORTS / "20260817-232634-dc66e49.pex-extract.json"
FLAT_REPORT = REPORTS / "20260817-232502-dc66e49.extract.json"

MERGED_LEG_PREFIX = mk.MERGED_GROUND_NODE + "__"


def _cards(lines: list[str]) -> list[list[str]]:
    return [line.split() for line in lines if line and not line.startswith("*")]


class MergedGroundParasiticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.extract = json.loads(RC_REPORT.read_text())
        cls.lines, cls.info = mk.emit(cls.extract)
        cls.cards = _cards(cls.lines)
        cls.devices = [c for c in cls.cards if c[0].startswith("X")]
        cls.resistors = [c for c in cls.cards if c[0].startswith("R")]
        cls.capacitors = [c for c in cls.cards if c[0].startswith("C")]
        cls.merged_net = next(
            n for n in cls.extract["parasitics"]["nets"] if n["net"] == mk.MERGED_GROUND_RAW
        )
        #: leg node -> (model, body rail) as it appears on the device card
        cls.leg_device = {}
        for card in cls.devices:
            drain, gate, source, body, model = card[1:6]
            for node in (drain, gate, source):
                if node.startswith(MERGED_LEG_PREFIX):
                    cls.leg_device[node] = (model, body)
        #: leg node -> hub node as it appears on the R card
        cls.leg_hub = {c[1]: c[2] for c in cls.resistors if c[1].startswith(MERGED_LEG_PREFIX)}

    # -- the star exists at all (issue #184's original report) ---------------

    def test_merged_ground_star_is_emitted_for_every_non_body_terminal(self) -> None:
        """297 ground-rail R legs -- the same count as the pre-#132 RC DUT.

        The extractor reports 596 terminals on the merged net; 299 are body
        terminals, which T4 binds directly to a real rail with no series R on
        every net, merged or not. The remaining 297 (144 D + 153 S) are the
        ground-rail legs #184 reported as missing.
        """
        non_body = [t for t in self.merged_net["terminals"] if t["terminal"].upper() != "B"]
        self.assertEqual(len(non_body), 297)
        self.assertEqual(len(self.leg_hub), 297)
        self.assertEqual(set(self.leg_hub), set(self.leg_device))

    def test_body_terminals_get_no_leg_resistor(self) -> None:
        body = [t for t in self.merged_net["terminals"] if t["terminal"].upper() == "B"]
        self.assertEqual(len(body), 299)
        emitted = {c[1] for c in self.resistors}
        for terminal in body:
            leg = mk.MERGED_GROUND_NODE + terminal["leg_net"][len(mk.MERGED_GROUND_RAW) :]
            self.assertNotIn(leg, emitted)

    def test_totals_match_the_pre_132_rc_dut(self) -> None:
        """2877 R restores the pre-#132 total exactly; C is 17, not 18.

        Pre-#132 the two rails were two nets, so the star loop emitted a cap
        for each: one between GND_DRV and the ground reference, and one from
        GND_LOGIC to the ground reference -- which *is* GND_LOGIC (BA3), i.e.
        a degenerate cap-to-itself card. The merged net has one measured
        capacitance and one non-degenerate place to put it, hence 17.
        """
        self.assertEqual(self.info["parasitics"], {"r": 2877, "c": 17})

    # -- per-device rebind, never a shared hub -------------------------------

    def test_each_leg_hub_is_that_legs_own_device_rail(self) -> None:
        """The whole point: hub is per-device, keyed by the device's own flavor.

        A shared hub would show up here as a hub node that does not match the
        device's own (class, L)-derived rail -- including the "plausible"
        wrong answers (one of the two real rails for *every* leg, or a fresh
        synthesized node standing in for the merged identity).
        """
        self.assertTrue(self.leg_hub, "no merged-ground legs emitted at all")
        for leg, hub in self.leg_hub.items():
            model, body = self.leg_device[leg]
            self.assertEqual(
                hub,
                body,
                f"leg {leg} ({model}) hubs on {hub}, not its own device's rail {body}",
            )

    def test_both_ground_domains_are_represented(self) -> None:
        """294 legs on GND_DRV, 3 on GND_LOGIC -- the pre-#132 split, exactly.

        Pre-#132 the extractor reported the two rails separately: GND_DRV with
        294 non-body terminals (150 S + 144 D) and GND_LOGIC with 3 (3 S). A
        single-rail collapse in either direction (297/0 or 0/297) is the
        signature of a shared hub and fails here.
        """
        self.assertEqual(Counter(self.leg_hub.values()), {"GND_DRV": 294, "GND_LOGIC": 3})
        by_model = Counter((self.leg_device[leg][0], hub) for leg, hub in self.leg_hub.items())
        self.assertEqual(by_model, {("nfet_06v0", "GND_DRV"): 294, ("nfet_03v3", "GND_LOGIC"): 3})

    def test_no_node_carries_the_merged_identity_or_a_shared_hub(self) -> None:
        """No card ever names the merged identity as a node.

        Covers both the raw form (illegal as an ngspice node name -- `|` is
        not a legal node character) and the renamed hub form: the merged
        identity may appear as a *leg* (`GND_DRV_GND_LOGIC__t<n>`) and as a
        card *name*, never as a bare hub node.
        """
        for card in self.cards:
            nodes = card[1:5] if card[0].startswith("X") else card[1:3]
            for node in nodes:
                self.assertNotIn("|", node)
                self.assertNotEqual(node, mk.MERGED_GROUND_NODE)
                self.assertNotEqual(node, mk.MERGED_GROUND_RAW)

    def test_every_merged_leg_node_is_referenced_exactly_twice(self) -> None:
        """One device terminal + one leg resistor: no dangling, no sharing.

        The dangling-island risk is what motivated skipping the star in the
        first place, so pin that the per-device form does not reintroduce it,
        and that two device terminals never end up sharing one leg node.
        """
        refs: Counter[str] = Counter()
        for card in self.cards:
            nodes = card[1:5] if card[0].startswith("X") else card[1:3]
            for node in nodes:
                refs[node] += 1
        for leg in self.leg_hub:
            self.assertEqual(refs[leg], 2, f"leg {leg} referenced {refs[leg]}x, expected 2")

    def test_no_dangling_node_anywhere_in_the_dut(self) -> None:
        refs: Counter[str] = Counter()
        for card in self.cards:
            nodes = card[1:5] if card[0].startswith("X") else card[1:3]
            for node in nodes:
                refs[node] += 1
        self.assertEqual([node for node, count in refs.items() if count < 2], [])

    # -- the inter-rail capacitance ------------------------------------------

    def test_inter_rail_capacitor_spans_the_two_real_rails(self) -> None:
        inter_rail = [c for c in self.capacitors if set(c[1:3]) == {"GND_DRV", "GND_LOGIC"}]
        self.assertEqual(len(inter_rail), 1, "expected exactly one GND_DRV<->GND_LOGIC cap")
        card = inter_rail[0]
        self.assertEqual(
            float(card[3]),
            float(mk._fmt(self.merged_net["capacitance_ff"] * 1e-15)),
            "the merged net's measured capacitance must be carried whole",
        )

    def test_every_other_capacitor_still_references_the_ground_reference(self) -> None:
        others = [c for c in self.capacitors if set(c[1:3]) != {"GND_DRV", "GND_LOGIC"}]
        self.assertEqual(len(others), 16)
        for card in others:
            self.assertEqual(card[2], mk.GROUND_REF)

    # -- the non-parasitic DUT is unaffected ---------------------------------

    def test_without_parasitics_merged_terminals_bind_straight_to_their_rail(self) -> None:
        """The `--combine` DUT has no legs to route through, so nothing changes.

        Its extraction carries no `parasitics` block, so a merged-ground
        terminal has no measured leg; it must still bind directly to the
        device's own real rail (the behavior issue #132 established), never
        to a leg node that no resistor would then terminate.
        """
        extract = json.loads(FLAT_REPORT.read_text())
        self.assertIsNone(extract.get("parasitics"))
        lines, info = mk.emit(extract, combine=True)
        self.assertEqual(info["parasitics"], {"r": 0, "c": 0})
        for card in _cards(lines):
            for node in card[1:5]:
                self.assertNotIn("|", node)
                self.assertFalse(node.startswith(MERGED_LEG_PREFIX))
        grounds = Counter(
            node
            for card in _cards(lines)
            for node in card[1:5]
            if node in ("GND_DRV", "GND_LOGIC")
        )
        self.assertTrue(grounds["GND_DRV"] and grounds["GND_LOGIC"])

    # -- the guard on an unexpected device flavor ----------------------------

    def test_a_pmos_terminal_on_the_merged_identity_is_an_error(self) -> None:
        """Never silently rebind a PMOS terminal to a *supply* rail.

        `_model_and_body` returns VDD_LOGIC/VDD_DRV for PMOS, so a PMOS
        terminal landing on the merged ground identity would otherwise be
        rebound to a supply -- a short, emitted without complaint.
        """
        extract = copy.deepcopy(self.extract)
        pfet = next(d for d in extract["devices"] if d["class"] == "pfet")
        terminal = next(
            t
            for n in extract["parasitics"]["nets"]
            if n["net"] == mk.MERGED_GROUND_RAW
            for t in n["terminals"]
            if t["terminal"].upper() != "B"
        )
        terminal["device"] = pfet["name"]
        terminal["terminal"] = "S"
        pfet["nets"]["s"] = mk.MERGED_GROUND_RAW
        with self.assertRaises(SystemExit):
            mk.emit(extract)


class AnonymousNetNameTest(unittest.TestCase):
    """``klt extract`` names an internal net with no schematic label ``$N``
    (its own anonymous-net convention) -- this design's first real case is
    issue #166's XCCOMP series stack, whose three inter-cap nodes (schematic
    ``nccomp1..3``) carry no label anywhere in the layout. A bare SPICE
    token that *starts* with ``$`` is an inline-comment marker to ngspice, so
    emitting one of these nets directly as a node silently truncates the
    rest of that card -- no simulator error, just a per-card ``... is not a
    valid ... line, ignored!`` warning outside this script's or
    ``run_corners.py``'s own PASS/FAIL summary (confirmed against a real
    post-#166 extraction: all four XCCOMP capacitor cards, plus every R/C
    leg on their own inter-cap nets, were silently dropped, and the
    resulting DUT measured *zero* effect from XCCOMP on any PVT corner,
    bit-for-bit -- issue #201). Built from a synthetic extract dict (not the
    RC_REPORT/FLAT_REPORT fixtures above, which predate #166 and carry no
    anonymous net) so this pins the transform even if those fixtures are
    never refreshed.
    """

    def test_spice_node_rewrites_a_leading_dollar(self) -> None:
        self.assertEqual(mk._spice_node("$18"), "ANON18")
        self.assertEqual(mk._spice_node("GND_DRV"), "GND_DRV")
        self.assertEqual(mk._spice_node("x1_ncb"), "x1_ncb")
        # mid-token '$' (e.g. an already-safe leg/instance name) is untouched
        self.assertEqual(mk._spice_node("R$18__t0"), "R$18__t0")

    @staticmethod
    def _synthetic_extract(*, with_parasitics: bool) -> dict:
        devices = [
            {
                "class": "nfet",
                "name": "M1",
                "params": {
                    "l_um": 0.28, "w_um": 5.0,
                    "ad_um2": 1.0, "as_um2": 1.0, "pd_um": 1.0, "ps_um": 1.0,
                },
                "nets": {"d": "$5", "g": "IN", "s": "GND_LOGIC", "b": "GND_LOGIC"},
            },
            {
                "class": "cap_mim_2f0_m4m5_noshield",
                "name": "$6",
                "params": {"c_f": 1e-14},
                "nets": {"a": "$5", "b": "OUT"},
            },
        ]
        extract: dict = {"devices": devices, "parasitics": None}
        if with_parasitics:
            extract["parasitics"] = {
                "nets": [
                    {
                        "net": "$5",
                        "hub_net": "$5",
                        "capacitance_ff": 1.0,
                        "terminals": [
                            {
                                "device": "M1", "terminal": "D",
                                "leg_net": "$5__t0", "resistance_ohm": 1.0,
                            },
                            {
                                "device": "$6", "terminal": "a",
                                "leg_net": "$5__t1", "resistance_ohm": 1.0,
                            },
                        ],
                    },
                ],
            }
        return extract

    def _assert_no_bare_dollar_token(self, lines: list[str]) -> None:
        for line in lines:
            if not line or line.startswith("*"):
                continue
            for token in line.split():
                self.assertFalse(
                    token.startswith("$"),
                    f"bare node/instance token starts with '$' (an ngspice "
                    f"inline-comment marker -- silently truncates the rest "
                    f"of the card): {line!r}",
                )

    def test_no_bare_dollar_token_without_parasitics(self) -> None:
        lines, _ = mk.emit(self._synthetic_extract(with_parasitics=False))
        self.assertTrue(lines)
        self._assert_no_bare_dollar_token(lines)

    def test_no_bare_dollar_token_with_parasitics(self) -> None:
        lines, _ = mk.emit(self._synthetic_extract(with_parasitics=True))
        self.assertTrue(lines)
        self._assert_no_bare_dollar_token(lines)


if __name__ == "__main__":
    unittest.main()
