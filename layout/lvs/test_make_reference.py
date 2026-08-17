#!/usr/bin/env python3
"""Unit tests for ``make_reference.py``'s deck-compatible reference build.

Stdlib-only, no ``klt``, no PDK -- runs on the PDK-free CI runner alongside
``layout/test_gen_gate_driver_core.py`` (``.github/workflows/ci.yml``'s
"Layout generator unit tests" step). Pins the two structural facts this
script's docstring documents as *measured against a real `klt extract` run*
(11 distinct PMOS body nets, one NMOS substrate net, generic ``nfet``/``pfet``
device-class tokens) so a change to the flattening/body-retargeting logic
that would silently break the committed ``status: match`` LVS evidence is
caught here first, without needing `klt`/the PDK to run this test.
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
        # gate_driver_core.provenance.json: 24 netlist devices, 959 transistors.
        self.assertEqual(self.info["devices"], 24)
        self.assertEqual(self.info["counts"], {"nfet": 299, "pfet": 660})

    def test_nfet_bodies_all_tie_to_the_synthesized_substrate_net(self) -> None:
        """Every extracted NMOS body compares against one global net.

        The gf180mcu extraction deck draws no p-substrate tap layer, so it
        ties every NMOS body to one synthesized net regardless of the
        schematic's own (domain-differentiated) body assignment -- confirmed
        against a real `klt extract` run (`num distinct nfet body nets: 1`).
        """
        nfet_lines = [
            line for line in self.text.splitlines() if line.startswith("M") and " nfet " in line
        ]
        self.assertEqual(len(nfet_lines), 299)
        bodies = {line.split()[4] for line in nfet_lines}
        self.assertEqual(bodies, {make_reference.SUBSTRATE_NET})

    def test_pfet_bodies_are_one_anonymous_net_per_schematic_instance(self) -> None:
        """11 distinct PMOS well nets, matching the layout's un-merged wells.

        Every PMOS device draws its own independent strip with its own local
        Nwell patch -- no well-merge geometry -- so `klt extract` measures 11
        distinct anonymous PMOS body nets (one per schematic PMOS instance),
        not 2 (one per voltage domain) or 1 (one shared band, as in
        gf180-bandgap's contiguous PMOS layout). Confirmed against a real
        `klt extract` run of the committed GDS.
        """
        pfet_lines = [
            line for line in self.text.splitlines() if line.startswith("M") and " pfet " in line
        ]
        self.assertEqual(len(pfet_lines), 660)
        bodies = {line.split()[4] for line in pfet_lines}
        self.assertEqual(len(bodies), 11)
        for body in bodies:
            self.assertTrue(body.startswith("nwl_"), body)

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
        """19 pins: 18 named schematic nets + the synthesized substrate net.

        Confirmed against a real `klt extract` run's ``pin_count``: every
        net named on a device terminal in the flattened schematic is
        promoted, plus ``vsubs``.
        """
        header = next(line for line in self.text.splitlines() if line.startswith(".SUBCKT"))
        pins = header.split()[2:]
        self.assertEqual(len(pins), 19)
        self.assertIn(make_reference.SUBSTRATE_NET, pins)
        self.assertEqual(pins, self.info["pins"])

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
        self.assertEqual(len(device_lines), 959)
        for line in device_lines:
            self.assertRegex(line, pattern)


if __name__ == "__main__":
    unittest.main()
