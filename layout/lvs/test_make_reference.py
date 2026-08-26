#!/usr/bin/env python3
"""Unit tests for ``make_reference.py``'s deck-compatible reference build.

Stdlib-only, no ``klt``, no PDK -- runs on the PDK-free CI runner alongside
``layout/test_gen_gate_driver_core.py`` (``.github/workflows/ci.yml``'s
"Layout generator unit tests" step). Pins the structural facts this script's
docstring documents as *measured against a real `klt extract` run* (PMOS
bodies tie to the schematic's own ``VDD_LOGIC``/``VDD_DRV``, one NMOS
substrate net, ``GND_LOGIC``/``GND_DRV`` merge into one net everywhere they
appear, generic ``nfet``/``pfet`` device-class tokens) so a change to the
flattening/body-retargeting logic that would silently break the committed
``status: match`` LVS evidence is caught here first, without needing
`klt`/the PDK to run this test.

Since issue #166 that also covers the ``XCCOMP*`` MiM stack (transform 6): the
C-card spelling that names a device class rather than inventing a third
terminal, the deck's own two-term capacitance value, the series node order,
and the fact that the stack's three interior nodes stay internal rather than
being promoted to pins.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import make_reference  # noqa: E402  (path set above)


class MakeReferenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text, self.info = make_reference.build_reference()

    def test_device_and_finger_counts_match_layout_provenance(self) -> None:
        # gate_driver_core.provenance.json still (correctly) publishes the
        # CURRENT, unregenerated GDS's counts (24 netlist devices, 959
        # transistors) -- issue #220 (schematic-only slice) added x3=uvlo (11
        # new netlist devices: 7 nfet_06v0 -- 6 at nf=1 m=1, one pulldown at
        # nf=1 m=800 -- and 4 pfet_06v0, all nf=1 m=1) to the committed
        # NETLIST only; regenerating the GDS to draw them is explicitly out
        # of scope for #220 and deferred to #221 (see
        # layout/test_gen_gate_driver_core.py's CommittedNetlistTest
        # docstring for the same transitional-gap note). This reference is
        # built directly from the netlist, so its counts track #220's netlist
        # change now: 24+11=35 devices, 299+806=1105 nfet / 660+4=664 pfet.
        self.assertEqual(self.info["devices"], 35)
        self.assertEqual(self.info["passives"], 4)
        self.assertEqual(self.info["resistors"], 4)
        # 271 drawn resistor units (12+16+3+240 for Rref/R1/R2/Rfb -- see
        # resistor_array_params()), not 4 -- each netlist R element is folded
        # into a series chain of unit devices, all of which must appear in
        # the reference (transform 7).
        self.assertEqual(
            self.info["counts"], {"nfet": 1105, "pfet": 664, "cap": 4, "res": 271}
        )

    def test_nfet_bodies_all_tie_to_the_global_substrate_identity(self) -> None:
        """Every extracted NMOS body compares against the one global identity.

        The gf180mcu extraction deck draws no p-substrate tap layer, so it
        ties every NMOS body to one deck-global identity regardless of the
        schematic's own (domain-differentiated) body assignment. Once real
        tie geometry is drawn for both grounds (issue #132), that global
        identity is itself directly wired to real labeled metal, so `klt
        extract` names it after that metal instead of its own synthesized
        `vsubs` placeholder -- confirmed against a real extraction (`vsubs`
        does not appear in the extracted netlist's pin list;
        `device.body_unverified` drops to zero for both device flavors).
        Issue #221 revision: under the currently-installed deck build, that
        real metal is `GND_LOGIC` alone (:data:`make_reference.BODY_NET`),
        not a `GND_DRV`-joined label -- see this module's docstring
        (transform 3) and `klayout-tools` issue #1149 for why.
        """
        nfet_lines = [
            line for line in self.text.splitlines() if line.startswith("M") and " nfet " in line
        ]
        # 299 + 806 (issue #220's x3=uvlo: 6 nfet_06v0 at nf=1 m=1 plus one
        # nf=1 m=800 pulldown) -- see test_device_and_finger_counts_match_
        # layout_provenance's comment for the transitional-gap context.
        self.assertEqual(len(nfet_lines), 1105)
        bodies = {line.split()[4] for line in nfet_lines}
        self.assertEqual(bodies, {make_reference.BODY_NET})

    def test_pfet_bodies_tie_to_the_schematics_own_supply_net(self) -> None:
        """PMOS bodies compare against VDD_LOGIC/VDD_DRV, not an anonymous net.

        Issue #132: every PMOS device now gets a real per-device well tie
        (``gen_gate_driver_core.Interconnect.body_ties()`` -- Comp+Nplus+
        Contact+Metal1 inside a redundant Nwell rectangle sized to merge with
        `klt gen mos_array`'s own internal well, wired to the device's own
        rail), which `klt`'s gf180mcu deck resolves via its `tap_nplus`
        derivation (klayout-tools issue #1084) into the device's own real
        body net -- confirmed against a real `klt extract` run:
        `unbiased_pmos_body_nets` drops from 660 entries to zero. So the
        reference now expects exactly the two real supply nets the schematic
        itself assigns (``VDD_LOGIC`` for the 3.3V group's one PMOS,
        ``VDD_DRV`` for the 5V/6V group's ten), not 11 anonymous
        per-instance placeholders.
        """
        pfet_lines = [
            line for line in self.text.splitlines() if line.startswith("M") and " pfet " in line
        ]
        # 660 + 4 (issue #220's x3=uvlo: 4 pfet_06v0, all nf=1 m=1) -- see
        # test_device_and_finger_counts_match_layout_provenance's comment.
        self.assertEqual(len(pfet_lines), 664)
        bodies = {line.split()[4] for line in pfet_lines}
        self.assertEqual(bodies, {"VDD_LOGIC", "VDD_DRV"})

    def test_device_class_is_generic_not_the_schematic_voltage_flavor(self) -> None:
        """`klt`'s gf180mcu deck extracts one device class per polarity.

        Using the schematic's flavored model name (``nfet_06v0``) here would
        make `klt lvs` see it as an unrelated device class from the layout's
        plain ``nfet``/``pfet`` and every device would report unmatched --
        confirmed against a real `klt lvs` run (see this module's docstring
        and ``make_reference.py``'s transform 2).
        """
        model_tokens = {line.split()[5] for line in self.text.splitlines() if line.startswith("M")}
        self.assertEqual(model_tokens, {"nfet", "pfet"})

    def test_pin_list_matches_extraction_promotion(self) -> None:
        """25 pins: 18 named schematic nets (pre-#220) plus issue #220's
        x3=uvlo's 7 new internal nets (nref, ndiv, ntail, ncompp, ncompn,
        lockout, uvlo_ok) -- ``GND_LOGIC``/``GND_DRV`` are not merged
        (transform 5, removed by issue #221; see this module's docstring and
        `klayout-tools` issue #1149).

        Confirmed against a real `klt extract` run's ``pin_count`` on the
        issue #221-extended GDS: every net named on a device terminal
        (source/drain/gate *and*, since issue #132, body) in the flattened
        schematic is promoted -- no separate synthesized ``vsubs`` pin,
        since real tie geometry resolves the deck's global substrate
        identity onto real labeled metal instead (transform 3, revised).
        """
        header = next(line for line in self.text.splitlines() if line.startswith(".SUBCKT"))
        pins = header.split()[2:]
        self.assertEqual(len(pins), 25)
        self.assertNotIn(make_reference.SUBSTRATE_NET, pins)
        self.assertEqual(pins, self.info["pins"])

    def test_gnd_logic_and_gnd_drv_are_separate_nets_except_on_body(self) -> None:
        """GND_LOGIC/GND_DRV stay two separate nets on every ordinary
        (non-body) terminal (issue #221 -- transform 5, removed).

        An earlier revision of this reference folded both names together
        everywhere, on the belief that real body-tie geometry for both
        grounds made `klt extract` merge them transitively via its global
        substrate identity. Re-running the *exact, byte-identical,
        previously-clean* pre-#221 GDS against the currently-installed `klt`
        build no longer reproduces that merge (`klayout-tools` issue #1149:
        deck substrate/well-tap recognition behavior changed between deck
        builds) -- `GND_DRV` extracts as its own, separate, unmerged pin on
        every terminal now. This also matches
        `spec/decision-records/0001` (Decision 1) better than the old
        assumption did: the two grounds are one electrical node only via an
        external pad ring this bare core block does not itself draw. Only
        the NMOS body terminal still canonicalizes, to the deck's one global
        substrate identity (``make_reference.BODY_NET``, ``"GND_LOGIC"``) --
        see ``test_nfet_bodies_all_tie_to_the_global_substrate_identity``.
        """
        header = next(line for line in self.text.splitlines() if line.startswith(".SUBCKT"))
        pins = header.split()[2:]
        self.assertIn("GND_LOGIC", pins)
        self.assertIn("GND_DRV", pins)
        device_lines = [line for line in self.text.splitlines() if line.startswith("M")]
        for line in device_lines:
            d, g, s, b = line.split()[1:5]
            # d/g/s: whichever of the two the schematic actually names,
            # unchanged -- never the other one, and never a joined label.
            for terminal in (d, g, s):
                self.assertNotIn("|", terminal)
            # body: always the one canonical identity.
            if " nfet " in line:
                self.assertEqual(b, make_reference.BODY_NET)

    def test_no_dollar_signs_or_backslashes(self) -> None:
        """ngspice treats a space-delimited ``$`` as an end-of-line comment.

        None of this script's own net/device names use `klt extract`'s
        anonymous ``$<n>`` spelling, so this is a standing invariant rather
        than a transform -- but worth pinning, since a stray one would
        silently truncate a device card rather than erroring.
        """
        self.assertNotIn("$", self.text)
        self.assertNotIn("\\", self.text)

    def test_regenerating_is_deterministic(self) -> None:
        text2, _info2 = make_reference.build_reference()
        self.assertEqual(self.text, text2)

    def test_every_device_line_is_well_formed(self) -> None:
        pattern = re.compile(
            r"^M\S+ \S+ \S+ \S+ \S+ (nfet|pfet) L=[\d.]+U W=[\d.]+U$"
        )
        device_lines = [line for line in self.text.splitlines() if line.startswith("M")]
        # 959 + 810 (issue #220's x3=uvlo, see
        # test_device_and_finger_counts_match_layout_provenance's comment).
        self.assertEqual(len(device_lines), 1769)
        for line in device_lines:
            self.assertRegex(line, pattern)

    # -- transform 6: the MiM compensation stack (issue #166) --------------- #

    def _cap_lines(self) -> list[str]:
        return [line for line in self.text.splitlines() if line.startswith("C")]

    def test_capacitor_cards_name_the_extraction_decks_own_device_class(self) -> None:
        """``C<name> <a> <b> <model> C=<value>`` -- the one spelling that works.

        ``NetlistSpiceReader`` reads ``C1 a b model value`` as a *three*-
        terminal capacitor-with-bulk (taking the model token for a third net)
        and ``C1 a b value`` as the generic ``CAP`` class; only the explicit
        ``C=`` form names a device class the layout side's own
        ``cap_mim_2f0_m4m5_noshield`` can pair with. Pinned here because the
        failure mode is silent -- both wrong spellings parse.
        """
        pattern = re.compile(
            r"^C\S+ \S+ \S+ cap_mim_2f0_m4m5_noshield C=[\d.e+-]+$"
        )
        lines = self._cap_lines()
        self.assertEqual(len(lines), 4)
        for line in lines:
            self.assertRegex(line, pattern)

    def test_capacitor_value_is_the_decks_two_term_mim_model(self) -> None:
        """5.4516e-14 F -- ``1.99e-15 * 25 + 2.383e-16 * 20``, hand-computed.

        ``kdb.NetlistComparer`` compares a matched device pair's parameters
        directly, so an area-only (one-term) value here would report a
        ``device.property`` mismatch on all four capacitors even though the
        layout is right.
        """
        for line in self._cap_lines():
            value = float(line.split("C=")[1])
            self.assertAlmostEqual(value, 5.4516e-14, delta=1e-19)

    def test_capacitor_chain_is_series_end_to_end(self) -> None:
        """x1_ncb -> nccomp1 -> nccomp2 -> nccomp3 -> IN_DRV, in that order.

        A parallel (or partly shorted) stack would have the same four cards
        and the same four values, and only the node sequence tells them apart
        -- the same property ``check_gate_driver_core``'s ``mim_stack`` check
        asserts on the *extracted* side.
        """
        by_name = {line.split()[0]: line.split()[1:3] for line in self._cap_lines()}
        self.assertEqual(
            [by_name[f"Cx1_XCCOMP{index}"] for index in range(1, 5)],
            [
                ["x1_ncb", "x1_nccomp1"],
                ["x1_nccomp1", "x1_nccomp2"],
                ["x1_nccomp2", "x1_nccomp3"],
                ["x1_nccomp3", "IN_DRV"],
            ],
        )

    def test_interior_series_nodes_are_not_pins(self) -> None:
        """The stack's floating nodes stay internal on both sides of the compare.

        The layout labels none of them (they are plate-to-plate metal with no
        via on it at all), so `klt extract` leaves them unnamed and internal;
        promoting them here would leave the reference with 20 pins against the
        layout's 17.
        """
        header = next(line for line in self.text.splitlines() if line.startswith(".SUBCKT"))
        pins = header.split()[2:]
        for node in ("x1_nccomp1", "x1_nccomp2", "x1_nccomp3"):
            self.assertNotIn(node, pins)
            self.assertIn(node, self.info["nets"])

    # -- transform 7: the uvlo bias resistor network (issue #221) ----------- #

    def _res_lines(self) -> list[str]:
        return [line for line in self.text.splitlines() if line.startswith("R")]

    def test_resistor_cards_name_the_extraction_decks_own_device_class(self) -> None:
        """``R<name>_<i> <a> <b> <w> ppolyf_u R=<value>`` -- confirmed against
        a real ``klt lvs`` run to be the one spelling that pairs a bare-``R``
        reference card with ``klt extract``'s own 3-terminal ``ppolyf_u``
        device (this module's docstring, transform 7). One card per *drawn*
        series unit (271: 12+16+3+240 for Rref/R1/R2/Rfb), not one per
        netlist ``R`` element -- a lumped single-device reference does not
        match the folded layout (confirmed against a real ``klt lvs`` run:
        0/1777 devices matched)."""
        pattern = re.compile(r"^R\S+ \S+ \S+ \S+ ppolyf_u R=[\d.e+-]+$")
        lines = self._res_lines()
        self.assertEqual(len(lines), 271)
        for line in lines:
            self.assertRegex(line, pattern)

    def test_resistor_series_chain_sums_to_the_schematics_own_ohms_value(self) -> None:
        """Each netlist resistor's series unit cards sum to its schematic
        ohms value -- the drawn geometry has to reproduce it
        (``resistor_array_params``/``resistor_ohms``), which is exactly the
        thing LVS checks."""
        totals: dict[str, float] = {}
        for line in self._res_lines():
            # "Rx3_Rref_0 ..." -> card name "Rx3_Rref", unit index "0".
            card_name = line.split()[0].rsplit("_", 1)[0]
            totals[card_name] = totals.get(card_name, 0.0) + float(line.split("R=")[1])
        for card_name, expected in {
            "Rx3_Rref": 800000.0,
            "Rx3_R1": 880000.0,
            "Rx3_R2": 200000.0,
            "Rx3_Rfb": 16000000.0,
        }.items():
            self.assertAlmostEqual(totals[card_name], expected, delta=expected * 1e-6)

    def test_resistor_chain_endpoints_are_the_schematics_own_nets(self) -> None:
        """The first/last unit of each chain lands on the resistor's own
        plus/minus net (issue #221's ``Rref``/``R1``/``R2``/``Rfb``), not an
        internal node."""
        lines_by_resistor: dict[str, list[str]] = {}
        for line in self._res_lines():
            name = line.split()[0].rsplit("_", 1)[0]
            lines_by_resistor.setdefault(name, []).append(line)
        expected_ends = {
            "Rx3_Rref": ("VDD_DRV", "x3_nref"),
            "Rx3_R1": ("VDD_DRV", "x3_ndiv"),
            # R2's minus is literally the schematic's own `GND_DRV` -- an
            # ordinary two-terminal connection, not the body/substrate
            # identity, so it keeps its own real name (issue #221; transform
            # 5, removed).
            "Rx3_R2": ("x3_ndiv", "GND_DRV"),
            "Rx3_Rfb": ("x3_uvlo_ok", "x3_ndiv"),
        }
        for name, (plus, minus) in expected_ends.items():
            first = sorted(lines_by_resistor[name], key=lambda ln: int(ln.split()[0].rsplit("_", 1)[1]))
            self.assertEqual(first[0].split()[1], plus)
            self.assertEqual(first[-1].split()[2], minus)

    def test_resistor_bulk_terminal_is_the_global_substrate_identity(self) -> None:
        """A resistor's 3rd (``w``) terminal ties to the same deck-global
        substrate identity every NMOS body does (transform 3)."""
        for line in self._res_lines():
            self.assertEqual(line.split()[3], make_reference.BODY_NET)


if __name__ == "__main__":
    unittest.main()
