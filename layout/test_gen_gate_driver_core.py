#!/usr/bin/env python3
"""Regression tests for the netlist-interpretation layer of the layout generator.

    python3 layout/test_gen_gate_driver_core.py     # or: python3 -m unittest ...

Standard-library ``unittest`` only, and deliberately **PDK-free and klt-free**:
everything under test here is pure netlist arithmetic in
``gen_gate_driver_core.py``, so this suite runs on a bare runner (the `test` job
in ``.github/workflows/ci.yml``) with nothing but ``python3``.

Why this file exists (issue #129)
---------------------------------

``check_gate_driver_core.py`` audits the committed GDS independently for
geometry, placement, connectivity and shorts -- but it imports ``parse_netlist``
and ``_spice_number`` from the generator, so it derives its *expected* device
list from the very interpretation the generator drew from. A misreading of
``W``/``nf``/``m`` is therefore common-mode: expected and extracted would agree
and the ``devices`` check would pass on a wrong layout.

This suite closes that blind spot by asserting the **hand-computed** result of
that interpretation. Every expected number below is written out literally; none
of them is produced by calling ``_spice_number`` or ``parse_netlist`` on the
same input, because those are the helpers under test.

The interpretation being pinned (both halves confirmed, not assumed):

* SPICE side -- ``W`` is a device's *total* width, split across ``nf`` fingers,
  and ``m`` replicates the whole device. gf180mcu's own model cards pass
  ``w=w nf=nf`` straight into the BSIM core and size their drift resistors on
  ``w/nf``; ``gate_driver_core.spice``'s own geometry expressions
  (``ad='int((nf+1)/2) * W/nf * 0.18u'``) use ``W/nf`` as the per-finger width.
* klt side -- ``klt gen mos_array``'s ``w_um`` is the *per-finger* width: with
  ``finger_topology: "parallel"`` the unit device is "one folded transistor of
  width ``fingers * w_um``" (klayout-tools ``docs/cli/gen.md``, and the same
  sentence in ``gen.py``'s ``_mos_unit_strapped_layout`` docstring). Confirmed
  empirically on klt 0.2.0: ``{"w_um": 1.0, "fingers": 2}`` extracts back as
  two parallel transistors of ``w_um: 1.0`` each.

So a netlist device must be drawn as ``nf*m`` fingers of width ``W/nf`` --
total drawn width ``W*m``, independent of ``nf``.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_gate_driver_core import (  # noqa: E402  (path set above)
    NETLIST_PATH,
    Device,
    GenError,
    Passive,
    _device_from_tokens,
    parse_netlist,
    parse_netlist_full,
)


def _device_line(params: str) -> list[str]:
    """One ``X<name> d g s b model <params>`` device line, as split tokens."""
    return f"XMTEST d g s b nfet_06v0 {params}".split()


class MultiFingerInterpretationTest(unittest.TestCase):
    """``nf>1`` must split ``W`` across fingers, not repeat it ``nf`` times."""

    def test_nf2_m1_splits_width_across_two_fingers(self):
        # W=20u split across nf=2 fingers -> 2 fingers of 10.0 um each.
        device = _device_from_tokens(
            _device_line("L=0.7u W=20u nf=2 m=1"), {}, prefix="x1_"
        )
        self.assertEqual(device.fingers, 2)
        self.assertAlmostEqual(device.w_um, 10.0, places=9)

    def test_nf2_m1_total_drawn_width_equals_netlist_W(self):
        # The invariant that makes the layout match the schematic: the total
        # width klt draws (fingers * w_um) is W*m -- here 20.0 um, NOT 40.0.
        device = _device_from_tokens(
            _device_line("L=0.7u W=20u nf=2 m=1"), {}, prefix="x1_"
        )
        self.assertAlmostEqual(device.fingers * device.w_um, 20.0, places=9)

    def test_nf4_m3_folds_fingers_and_multiplicity(self):
        # W=12u / nf=4 -> 3.0 um per finger; nf*m = 4*3 = 12 fingers drawn;
        # total drawn width 36.0 um = W*m.
        device = _device_from_tokens(
            _device_line("L=0.7u W=12u nf=4 m=3"), {}, prefix="x1_"
        )
        self.assertEqual(device.fingers, 12)
        self.assertAlmostEqual(device.w_um, 3.0, places=9)
        self.assertAlmostEqual(device.fingers * device.w_um, 36.0, places=9)

    def test_nf_does_not_change_total_width(self):
        # Same device, three legal finger splits of the same 24 um total.
        for nf, expected_w_um in ((1, 24.0), (2, 12.0), (3, 8.0)):
            with self.subTest(nf=nf):
                device = _device_from_tokens(
                    _device_line(f"L=0.7u W=24u nf={nf} m=2"), {}, prefix="x1_"
                )
                self.assertEqual(device.fingers, nf * 2)
                self.assertAlmostEqual(device.w_um, expected_w_um, places=9)
                self.assertAlmostEqual(
                    device.fingers * device.w_um, 48.0, places=9
                )


class SingleFingerUnchangedTest(unittest.TestCase):
    """``nf=1`` (every device in the committed netlist) must not move at all."""

    def test_nf1_m1_is_one_finger_of_full_width(self):
        device = _device_from_tokens(
            _device_line("L=0.55u W=4.4u nf=1 m=1"), {}, prefix="x2_"
        )
        self.assertEqual(device.fingers, 1)
        self.assertAlmostEqual(device.w_um, 4.4, places=9)

    def test_nf1_m500_is_500_fingers_of_full_width(self):
        # x2_XMP6, the final output pfet: W=10u, nf=1, m=500.
        device = _device_from_tokens(
            _device_line("L=0.55u W=10.0u nf=1 m=500"), {}, prefix="x2_"
        )
        self.assertEqual(device.fingers, 500)
        self.assertAlmostEqual(device.w_um, 10.0, places=9)

    def test_missing_nf_and_m_default_to_one(self):
        device = _device_from_tokens(_device_line("L=0.28u W=5u"), {}, prefix="x1_")
        self.assertEqual(device.fingers, 1)
        self.assertAlmostEqual(device.w_um, 5.0, places=9)


class DegenerateParamsTest(unittest.TestCase):
    """``nf``/``m`` below 1 are netlist errors, not silently-clamped values."""

    def test_nf_zero_raises(self):
        with self.assertRaises(GenError):
            _device_from_tokens(
                _device_line("L=0.7u W=20u nf=0 m=1"), {}, prefix="x1_"
            )

    def test_m_zero_raises(self):
        with self.assertRaises(GenError):
            _device_from_tokens(
                _device_line("L=0.7u W=20u nf=1 m=0"), {}, prefix="x1_"
            )


class CommittedNetlistTest(unittest.TestCase):
    """The committed netlist is all ``nf=1``, so the committed GDS is unaffected.

    Both numbers below are the ones ``layout/README.md`` and
    ``gate_driver_core.provenance.json`` publish; they are hard-coded here so
    that a future netlist edit which *does* change the drawn transistor count
    fails this suite instead of silently invalidating the committed GDS's
    ``sha256``.
    """

    def test_every_committed_device_line_is_nf1(self):
        # Read as raw text rather than through parse_netlist -- this assertion
        # is what licenses the "no behavior change" claim, so it must not go
        # through the parser under test.
        with open(NETLIST_PATH, encoding="utf-8") as handle:
            text = handle.read()
        nf_values = re.findall(r"\bnf=(\S+)", text)
        self.assertEqual(len(nf_values), 24)
        self.assertEqual(set(nf_values), {"1"})

    def test_committed_netlist_device_and_transistor_counts(self):
        _ports, devices = parse_netlist(NETLIST_PATH)
        self.assertEqual(len(devices), 24)
        self.assertEqual(sum(d.fingers for d in devices), 959)


class PassiveDeviceTest(unittest.TestCase):
    """Non-MOS device lines are classified, not misread as transistors.

    Issue #155 added ``XCCOMP``, a MIM feedforward compensation capacitor, to
    the netlist. It carries ``c_width``/``c_length`` and two terminals rather
    than a MOSFET's ``W``/``L`` and four, which the position-based parser read
    as "model = ``c_width=3.0u``" and then crashed on with ``KeyError: 'W'``.
    The parser now locates the model as the last token before the first
    parameter, so both device shapes parse, and a capacitor is returned as a
    :class:`Passive` -- a distinct type from :class:`Device`, so it can never
    reach ``klt gen mos_array`` as if it were a transistor.

    The capacitor is deliberately *not* drawn by the generator (``klt gen`` has
    no capacitor generator, and the metal pair is a deferred layout-time
    choice) -- issue #166 owns drawing it and re-running DRC/LVS. What this
    suite pins is that the skip is explicit and visible: the passive appears in
    ``parse_netlist_full``'s third return value, so ``build()`` can warn and
    record it, and never in the MOS device list the layout is generated from.
    """

    CAP_LINE = "XCCOMP ncb out cap_mim_1f0_m4m5_noshield c_width=3.0u c_length=3.0u m=1"

    def test_mim_cap_line_parses_as_a_passive(self):
        passive = _device_from_tokens(self.CAP_LINE.split(), {}, prefix="x1_")
        self.assertIsInstance(passive, Passive)
        self.assertNotIsInstance(passive, Device)
        self.assertEqual(passive.name, "x1_XCCOMP")
        self.assertEqual(passive.model, "cap_mim_1f0_m4m5_noshield")
        self.assertAlmostEqual(passive.w_um, 3.0, places=9)
        self.assertAlmostEqual(passive.l_um, 3.0, places=9)
        self.assertEqual(passive.multiplicity, 1)

    def test_passive_terminals_resolve_through_the_instance_mapping(self):
        # `out` is a formal port of level_shifter, wired to IN_DRV at the top
        # level; `ncb` is internal, so it takes the instance prefix.
        passive = _device_from_tokens(
            self.CAP_LINE.split(), {"out": "IN_DRV"}, prefix="x1_"
        )
        self.assertEqual(passive.plus, "x1_ncb")
        self.assertEqual(passive.minus, "IN_DRV")

    def test_committed_netlist_has_exactly_one_undrawn_passive(self):
        _ports, devices, passives = parse_netlist_full(NETLIST_PATH)
        self.assertEqual(len(devices), 24)
        self.assertEqual([p.name for p in passives], ["x1_XCCOMP"])
        self.assertEqual(passives[0].minus, "IN_DRV")
        # The MOS list the layout is generated from must contain no passive.
        self.assertTrue(all(isinstance(d, Device) for d in devices))
        self.assertNotIn("cap_mim_1f0_m4m5_noshield", {d.model for d in devices})

    def test_passive_is_reported_in_full_but_hidden_from_the_mos_parser(self):
        ports_a, devices_a = parse_netlist(NETLIST_PATH)
        ports_b, devices_b, _passives = parse_netlist_full(NETLIST_PATH)
        self.assertEqual(ports_a, ports_b)
        self.assertEqual([d.name for d in devices_a], [d.name for d in devices_b])


class MalformedDeviceLineTest(unittest.TestCase):
    """An unclassifiable device line raises ``GenError``, never a bare KeyError.

    Silently dropping a netlist device would produce a GDS that does not
    implement the schematic, so every rejection here is deliberate and loud.
    """

    def test_mos_line_without_W_raises_gen_error_not_keyerror(self):
        with self.assertRaises(GenError) as ctx:
            _device_from_tokens("XMTEST d g s b nfet_06v0 L=0.7u m=1".split(), {}, "x1_")
        self.assertIn("W", str(ctx.exception))

    def test_unknown_two_terminal_model_raises(self):
        with self.assertRaises(GenError):
            _device_from_tokens("XRTEST a b res_generic r=1k".split(), {}, "x1_")

    def test_passive_without_geometry_raises(self):
        with self.assertRaises(GenError):
            _device_from_tokens("XCTEST a b cap_mim_1f0_m4m5_noshield m=1".split(), {}, "x1_")

    def test_passive_with_wrong_terminal_count_raises(self):
        with self.assertRaises(GenError):
            _device_from_tokens(
                "XCTEST a b c cap_mim_1f0_m4m5_noshield c_width=3.0u c_length=3.0u".split(),
                {},
                "x1_",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
