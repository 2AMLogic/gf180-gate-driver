#!/usr/bin/env python3
"""Regression tests for the netlist-interpretation layer of the layout generator.

    python3 layout/test_gen_gate_driver_core.py     # or: python3 -m unittest ...

Standard-library ``unittest`` only, and deliberately **PDK-free and klt-free**:
everything under test here is pure arithmetic over a netlist or over an already
captured `klt` response, so this suite runs on a bare runner (the `test` job in
``.github/workflows/ci.yml``) with nothing but ``python3``.

Three things are pinned here, for three different reasons:

* the **netlist interpretation** in ``gen_gate_driver_core.py`` (issue #129) --
  see below;
* the **ground-rail isolation verdict** in ``check_gate_driver_core.py``
  (issue #132) -- ``ground_rail_isolation_verdict()`` is the only remaining
  automated signal that would catch a real short between ``GND_LOGIC`` and
  ``GND_DRV`` in the drawn interconnect, and its failing directions cannot be
  produced from the committed (correct) GDS, so they are exercised against
  synthetic ``klt components`` responses instead.  That function is pure by
  design precisely so this suite can reach it;
* the **MiM stack verdict** in ``check_gate_driver_core.py`` (issue #166) --
  ``mim_stack_verdict()`` is what states, mechanically, that the compensation
  stack's interior nodes are genuinely floating and that the four capacitors
  are in *series* rather than merely present.  Same argument as above: every
  one of its failing directions is unreachable from the committed GDS, so they
  are exercised from synthetic extraction facts, and the function is pure so
  they can be.

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

from check_gate_driver_core import (  # noqa: E402  (path set above)
    ground_rail_isolation_verdict,
    mim_stack_verdict,
    routed_nets,
)
from gen_gate_driver_core import (  # noqa: E402  (path set above)
    NETLIST_PATH,
    Device,
    GenError,
    Interconnect,
    Passive,
    Resistor,
    _device_from_tokens,
    _resistor_from_tokens,
    parse_netlist,
    parse_netlist_full,
    resistor_array_params,
    resistor_ohms,
)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lvs"))

from make_reference import mim_capacitance_f  # noqa: E402  (path set above)


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
    """The committed netlist is all ``nf=1``; this pins the netlist-side count.

    Historically both numbers here also matched ``layout/README.md`` and
    ``gate_driver_core.provenance.json`` (24 devices / 959 transistors) --
    they were the same fact read two ways, so a netlist edit that changed the
    drawn transistor count would fail this suite instead of silently
    invalidating the committed GDS's ``sha256``.

    Issue #220 (schematic-only slice) added `x3=uvlo` -- 11 new transistors,
    10 at `nf=1 m=1` and one large pulldown at `nf=1 m=800` -- to
    `design/gate_driver_core.sch` / `design/netlist/gate_driver_core.spice`,
    per that issue's own explicit deliverable ("gate_driver_core.sch
    instantiates UVLO... regenerated and committed") and epic #542's stated
    phase split ("schematic + pre-layout sim -> layout + post-layout sim").
    Layout/DRC/LVS -- including regenerating the committed GDS to draw the
    new UVLO transistors -- is explicitly out of scope for #220 and deferred
    to #221 ("layout extension needs this schematic + netlist as its LVS
    reference"). The numbers below are therefore intentionally updated to
    match the new committed *netlist* (24 + 11 = 35 devices, 959 + 810 = 1769
    fingers) ahead of the GDS: `layout/README.md` and
    `gate_driver_core.provenance.json` still (correctly) describe the
    CURRENT, unregenerated GDS (24 devices / 959 transistors) until #221
    regenerates it -- that divergence is the expected, tracked state of this
    transition, not a bug either document should silently paper over.
    """

    def test_every_committed_device_line_is_nf1(self):
        # Read as raw text rather than through parse_netlist -- this assertion
        # is what licenses the "no behavior change [to nf]" claim, so it must
        # not go through the parser under test.
        with open(NETLIST_PATH, encoding="utf-8") as handle:
            text = handle.read()
        nf_values = re.findall(r"\bnf=(\S+)", text)
        self.assertEqual(len(nf_values), 35)
        self.assertEqual(set(nf_values), {"1"})

    def test_committed_netlist_device_and_transistor_counts(self):
        _ports, devices = parse_netlist(NETLIST_PATH)
        self.assertEqual(len(devices), 35)
        self.assertEqual(sum(d.fingers for d in devices), 1769)


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

    Issue #192 (spec/decision-records/0014) then replaced that single device
    with **four series** ``cap_mim_2f0_m4m5_noshield`` devices at the DRM
    minimum 5.0 um x 5.0 um: ``gf180mcuD`` fixes the MiM density at
    2 fF/um^2, so the ``cap_mim_1f0_*`` model has no fabricable or
    LVS-recognizable device here, and DRM rule MIMTM.8a's 25 um^2 minimum MIM
    area makes the smallest legal single device ~54.5 fF -- four times too
    large for this node. This suite therefore also pins that the passive
    *chain* is read end to end (``x1.ncb`` -> ``nccomp1..3`` -> ``IN_DRV``),
    since a parser that silently dropped one link would leave a plausible but
    wrong effective capacitance.

    Issue #166 then drew them: ``klt gen`` still has no capacitor generator,
    so ``Interconnect.mim_caps()`` draws the plate/marker/via geometry through
    ``klt draw`` instead.  What this suite pins is the *parsing* half of that
    handoff -- each capacitor appears in ``parse_netlist_full``'s third return
    value (a :class:`Passive`, never a :class:`Device`), which is what keeps
    it out of ``klt gen mos_array``'s hands and gives ``mim_caps()`` the chain
    it draws from.
    """

    CAP_LINE = "XCCOMP1 ncb nccomp1 cap_mim_2f0_m4m5_noshield c_width=5.0u c_length=5.0u m=1"

    def test_mim_cap_line_parses_as_a_passive(self):
        passive = _device_from_tokens(self.CAP_LINE.split(), {}, prefix="x1_")
        self.assertIsInstance(passive, Passive)
        self.assertNotIsInstance(passive, Device)
        self.assertEqual(passive.name, "x1_XCCOMP1")
        self.assertEqual(passive.model, "cap_mim_2f0_m4m5_noshield")
        self.assertAlmostEqual(passive.w_um, 5.0, places=9)
        self.assertAlmostEqual(passive.l_um, 5.0, places=9)
        self.assertEqual(passive.multiplicity, 1)

    def test_passive_terminals_resolve_through_the_instance_mapping(self):
        # `out` is a formal port of level_shifter, wired to IN_DRV at the top
        # level; `ncb` and the stack's internal `nccomp*` nodes are internal,
        # so they take the instance prefix.
        last_link = (
            "XCCOMP4 nccomp3 out cap_mim_2f0_m4m5_noshield "
            "c_width=5.0u c_length=5.0u m=1"
        )
        passive = _device_from_tokens(
            last_link.split(), {"out": "IN_DRV"}, prefix="x1_"
        )
        self.assertEqual(passive.plus, "x1_nccomp3")
        self.assertEqual(passive.minus, "IN_DRV")

    def test_committed_netlist_has_four_passives_in_series(self):
        # Device count updated to 35 by issue #220 (x3=uvlo) -- see
        # CommittedNetlistTest's docstring above; the passive (MIM cap) chain
        # itself is untouched by that change, still 4 devices in series.
        _ports, devices, passives, _resistors = parse_netlist_full(NETLIST_PATH)
        self.assertEqual(len(devices), 35)
        self.assertEqual(
            [p.name for p in passives],
            ["x1_XCCOMP1", "x1_XCCOMP2", "x1_XCCOMP3", "x1_XCCOMP4"],
        )
        # Every device is the one MIM `gf180mcuD` can actually build, at the
        # DRM MIMTM.8a minimum area (25 um^2) -- decision record 0014.
        for p in passives:
            self.assertEqual(p.model, "cap_mim_2f0_m4m5_noshield")
            self.assertAlmostEqual(p.w_um, 5.0, places=9)
            self.assertAlmostEqual(p.l_um, 5.0, places=9)
            self.assertGreaterEqual(p.w_um * p.l_um, 25.0)
        # The chain must run end to end: x1.ncb -> nccomp1..3 -> IN_DRV. A
        # dropped or mis-ordered link would still simulate, just at the wrong
        # effective capacitance, so pin the topology and not only the count.
        self.assertEqual(
            [(p.plus, p.minus) for p in passives],
            [
                ("x1_ncb", "x1_nccomp1"),
                ("x1_nccomp1", "x1_nccomp2"),
                ("x1_nccomp2", "x1_nccomp3"),
                ("x1_nccomp3", "IN_DRV"),
            ],
        )
        # The MOS list the layout is generated from must contain no passive.
        self.assertTrue(all(isinstance(d, Device) for d in devices))
        self.assertNotIn("cap_mim_2f0_m4m5_noshield", {d.model for d in devices})
        # The non-fabricable 1 fF/um^2 model must not come back.
        self.assertNotIn(
            "cap_mim_1f0_m4m5_noshield",
            {d.model for d in devices} | {p.model for p in passives},
        )

    def test_passive_is_reported_in_full_but_hidden_from_the_mos_parser(self):
        ports_a, devices_a = parse_netlist(NETLIST_PATH)
        ports_b, devices_b, _passives, _resistors = parse_netlist_full(NETLIST_PATH)
        self.assertEqual(ports_a, ports_b)
        self.assertEqual([d.name for d in devices_a], [d.name for d in devices_b])


class ResistorDeviceTest(unittest.TestCase):
    """``uvlo``'s bare-``R`` bias resistors parse and size correctly (issue #221).

    ``design/netlist/uvlo.spice``'s ``Rref``/``R1``/``R2``/``Rfb`` are ideal
    SPICE ``R`` elements (an ohms value, no drawn geometry) -- unlike
    :class:`Device`/:class:`Passive`, which both come from ``X`` lines naming
    a model.
    """

    def test_bare_resistor_line_parses(self):
        resistor = _resistor_from_tokens(
            "Rref VDD_DRV nref 800k m=1".split(), {}, prefix="x3_"
        )
        self.assertIsInstance(resistor, Resistor)
        self.assertEqual(resistor.name, "x3_Rref")
        self.assertAlmostEqual(resistor.value_ohm, 800000.0, places=3)
        self.assertEqual(resistor.plus, "x3_VDD_DRV")
        self.assertEqual(resistor.minus, "x3_nref")

    def test_resistor_terminals_resolve_through_the_instance_mapping(self):
        resistor = _resistor_from_tokens(
            "Rref VDD_DRV nref 800k m=1".split(), {"VDD_DRV": "VDD_DRV"}, prefix="x3_"
        )
        self.assertEqual(resistor.plus, "VDD_DRV")
        self.assertEqual(resistor.minus, "x3_nref")

    def test_m_other_than_one_raises(self):
        with self.assertRaises(GenError):
            _resistor_from_tokens("R1 a b 100k m=2".split(), {}, prefix="")

    def test_committed_netlist_has_four_resistors(self):
        _ports, devices, _passives, resistors = parse_netlist_full(NETLIST_PATH)
        self.assertEqual(len(devices), 35)
        self.assertEqual(
            [(r.name, r.value_ohm, r.plus, r.minus) for r in resistors],
            [
                ("x3_Rref", 800000.0, "VDD_DRV", "x3_nref"),
                ("x3_R1", 880000.0, "VDD_DRV", "x3_ndiv"),
                ("x3_R2", 200000.0, "x3_ndiv", "GND_DRV"),
                ("x3_Rfb", 16000000.0, "x3_uvlo_ok", "x3_ndiv"),
            ],
        )

    def test_resistor_array_params_reproduce_the_target_value_exactly(self):
        """``resistor_ohms`` inverts ``resistor_array_params`` bit-for-bit.

        This is what makes the LVS reference (``make_reference.py`` transform
        7) and the drawn geometry agree: both call these two functions on the
        same ``value_ohm``.
        """
        for value_ohm in (800000.0, 880000.0, 200000.0, 16000000.0, 1.0, 1e9):
            num, rows, length_um = resistor_array_params(value_ohm)
            self.assertGreaterEqual(num, 1)
            self.assertGreaterEqual(rows, 1)
            self.assertGreater(length_um, 0.0)
            self.assertAlmostEqual(resistor_ohms(num, length_um), value_ohm, delta=value_ohm * 1e-9)

    def test_resistor_array_params_folds_a_large_value_into_multiple_rows(self):
        # Rfb=16 Mohm would be a single ~19.2mm strip undrawn -- must fold.
        num, rows, length_um = resistor_array_params(16_000_000.0)
        self.assertGreater(num, 1)
        self.assertGreater(rows, 1)
        self.assertLessEqual(length_um, 80.0 + 1e-9)

    def test_zero_or_negative_value_raises(self):
        with self.assertRaises(GenError):
            resistor_array_params(0.0)
        with self.assertRaises(GenError):
            resistor_array_params(-100.0)


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


class GroundRailIsolationVerdictTest(unittest.TestCase):
    """``check_gate_driver_core.ground_rail_isolation_verdict`` rules correctly.

    Issue #132 draws real substrate-tie geometry for both grounds, which makes
    `klt extract` report ``GND_LOGIC``/``GND_DRV`` as one merged net
    (klayout-tools #1128).  Neither ``klt lvs`` nor the ``devices`` check can
    tell the two rails apart any more, and DRC never could (two overlapping
    same-layer shapes on different nets merge into one polygon with no spacing
    violation to raise).  The ``ground_rail_isolation`` check is the only thing
    left that would catch a real short in the drawn interconnect -- so its
    *failing* directions have to be pinned, not just its passing one.

    The failing cases cannot be produced from the committed stream by
    construction (the layout is correct), so they are exercised here against
    synthetic ``klt components`` responses.  The verdict function is pure --
    response dict in, check record out -- so this stays PDK-free and klt-free
    like the rest of this suite, and runs on the bare CI runner.
    """

    NETS = ["GND_DRV", "GND_LOGIC", "OUT", "VDD_DRV"]

    @staticmethod
    def _component(cid, nets):
        return {
            "id": cid,
            "labels": list(nets),
            "conductors": [
                {"name": "m1", "layer": [34, 0], "shape_count": 7},
                {"name": "m2", "layer": [36, 0], "shape_count": 2},
            ],
            "vias": [{"name": "via1", "layer": [35, 0], "shape_count": 4}],
        }

    def _response(self, grouping):
        return {
            "components": [
                self._component(f"gate_driver_core:{index}", nets)
                for index, nets in enumerate(grouping)
            ]
        }

    def test_one_component_per_net_passes(self):
        """The shape the committed GDS actually has: 4 nets, 4 components."""
        verdict = ground_rail_isolation_verdict(
            self._response([[net] for net in self.NETS]), self.NETS
        )
        self.assertTrue(verdict["passed"], verdict["failures"])
        self.assertEqual(verdict["failures"], [])
        self.assertEqual(verdict["component_count"], 4)
        self.assertNotEqual(
            verdict["ground_components"]["GND_DRV"],
            verdict["ground_components"]["GND_LOGIC"],
        )

    def test_shorted_grounds_fail(self):
        """The exact failure this check exists for -- and LVS can no longer see."""
        verdict = ground_rail_isolation_verdict(
            self._response([["GND_DRV", "GND_LOGIC"], ["OUT"], ["VDD_DRV"]]), self.NETS
        )
        self.assertFalse(verdict["passed"])
        joined = " ".join(verdict["failures"])
        self.assertIn("GND_DRV", joined)
        self.assertIn("GND_LOGIC", joined)
        self.assertIn("shorted", joined)

    def test_shorted_signal_pair_also_fails(self):
        """The ruling is over all nets, not special-cased to the two grounds."""
        verdict = ground_rail_isolation_verdict(
            self._response([["GND_DRV"], ["GND_LOGIC"], ["OUT", "VDD_DRV"]]), self.NETS
        )
        self.assertFalse(verdict["passed"])
        self.assertIn("OUT, VDD_DRV", " ".join(verdict["failures"]))

    def test_missing_net_fails_instead_of_passing_vacuously(self):
        """A dropped rail/label must fail, not make "no two names" trivially true."""
        verdict = ground_rail_isolation_verdict(
            self._response([["GND_DRV"], ["OUT"], ["VDD_DRV"]]), self.NETS
        )
        self.assertFalse(verdict["passed"])
        self.assertIn("GND_LOGIC", " ".join(verdict["failures"]))

    def test_split_net_fails(self):
        """One net across two unconnected components is a drawn open."""
        verdict = ground_rail_isolation_verdict(
            self._response([["GND_DRV"], ["GND_LOGIC"], ["OUT"], ["VDD_DRV"], ["OUT"]]),
            self.NETS,
        )
        self.assertFalse(verdict["passed"])
        self.assertIn("split across 2", " ".join(verdict["failures"]))

    def test_routed_nets_matches_the_generators_own_rail_set(self):
        """The expected-net list is the same {d, g, s} set the generator rails."""
        _ports, devices = parse_netlist(NETLIST_PATH)
        nets = routed_nets(devices)
        self.assertEqual(nets, sorted(set(nets)))
        for ground in ("GND_LOGIC", "GND_DRV"):
            self.assertIn(ground, nets)


class MimStackVerdictTest(unittest.TestCase):
    """``check_gate_driver_core.mim_stack_verdict`` rules correctly (issue #166).

    The compensation stack's three interior nodes (``nccomp1``..``3``) are
    floating plate-to-plate nets with no DC path.  A stray strap, tie or
    shield on one of them changes the effective series capacitance without
    necessarily failing anything else: DRC rules on geometry, and LVS compares
    against a reference built from the same netlist.  ``mim_stack_verdict()``
    is what states the property mechanically -- so, exactly like the
    ground-rail verdict above, its *failing* directions have to be pinned even
    though the committed GDS cannot produce them.

    The function is pure (extraction facts in, check record out), so this
    stays PDK-free and klt-free.
    """

    CHAIN = ["x1_ncb", "x1_nccomp1", "x1_nccomp2", "x1_nccomp3", "IN_DRV"]
    #: The three interior nodes as `klt extract` actually reports them: the
    #: layout labels none of them, so they come back as generated names.
    ANON = ["$18", "$19", "$20"]

    def _passives(self):
        return [
            Passive(
                name=f"x1_XCCOMP{index + 1}",
                model="cap_mim_2f0_m4m5_noshield",
                w_um=5.0,
                l_um=5.0,
                multiplicity=1,
                plus=self.CHAIN[index],
                minus=self.CHAIN[index + 1],
            )
            for index in range(4)
        ]

    @staticmethod
    def _cap(name, a, b, width="5U", length="5U"):
        return {
            "name": name,
            "model": "cap_mim_2f0_m4m5_noshield",
            "a": a,
            "b": b,
            "params": {"c_width": width, "c_length": length},
        }

    def _series(self):
        """The shape the committed GDS actually has: a 4-deep series chain."""
        nodes = ["x1_ncb", *self.ANON, "IN_DRV"]
        return [
            self._cap(f"X$96{index}", nodes[index], nodes[index + 1])
            for index in range(4)
        ]

    PINS = ["x1_ncb", "IN_DRV", "OUT"]
    MOS_NETS = {"x1_ncb", "IN_DRV", "OUT", "VDD_DRV"}

    def _verdict(self, capacitors, mos_nets=None, pins=None):
        return mim_stack_verdict(
            capacitors,
            self.MOS_NETS if mos_nets is None else mos_nets,
            self.PINS if pins is None else pins,
            self._passives(),
        )

    def test_series_chain_passes(self):
        verdict = self._verdict(self._series())
        self.assertTrue(verdict["passed"], verdict["failures"])
        self.assertEqual(verdict["chain"], ["x1_ncb", *self.ANON, "IN_DRV"])
        self.assertEqual(
            [node["capacitor_terminals"] for node in verdict["interior_nodes"]],
            [2, 2, 2],
        )

    def test_missing_capacitor_fails(self):
        verdict = self._verdict(self._series()[:3])
        self.assertFalse(verdict["passed"])
        self.assertIn("3 capacitor(s) extracted", " ".join(verdict["failures"]))

    def test_parallel_stack_fails_despite_the_right_device_count(self):
        """Four caps between the same two nodes: same count, wrong topology."""
        verdict = self._verdict(
            [self._cap(f"X$96{index}", "x1_ncb", "IN_DRV") for index in range(4)]
        )
        self.assertFalse(verdict["passed"])
        self.assertIn("unvisited capacitor", " ".join(verdict["failures"]))

    def test_interior_node_tied_to_a_transistor_fails(self):
        """The primary correctness risk: a floating node that is not floating."""
        verdict = self._verdict(
            self._series(), mos_nets=self.MOS_NETS | {self.ANON[1]}
        )
        self.assertFalse(verdict["passed"])
        joined = " ".join(verdict["failures"])
        self.assertIn(self.ANON[1], joined)
        self.assertIn("not floating", joined)

    def test_interior_node_promoted_to_a_pin_fails(self):
        """A label (or a real connection) on a plate-to-plate node."""
        verdict = self._verdict(self._series(), pins=[*self.PINS, self.ANON[0]])
        self.assertFalse(verdict["passed"])
        self.assertIn("top-level pin", " ".join(verdict["failures"]))

    def test_wrong_plate_geometry_fails(self):
        """A plate drawn at the pre-#192 size would still extract and still be
        wrong -- 3.0 x 3.0 um is 9 um^2, under DRM MIMTM.8a's 25 um^2 floor."""
        capacitors = self._series()
        capacitors[2] = self._cap(
            capacitors[2]["name"],
            capacitors[2]["a"],
            capacitors[2]["b"],
            width="3U",
            length="3U",
        )
        verdict = self._verdict(capacitors)
        self.assertFalse(verdict["passed"])
        self.assertIn("which no schematic capacitor asks for", " ".join(verdict["failures"]))


class MimSeriesChainDrawTest(unittest.TestCase):
    """``Interconnect._mim_series_chain`` refuses to draw a chain it misread.

    ``mim_caps()``'s whole scheme -- every interior series node is a *shared
    plate*, so it cannot be strapped to anything -- only holds if the passives
    really are one even-length series chain.  Drawing from a misread chain
    would produce four legal-looking, DRC-clean capacitors implementing a
    different effective capacitance than spec/decision-records/0014 ratified,
    so each way of misreading it raises instead.
    """

    @staticmethod
    def _cap(name, plus, minus, model="cap_mim_2f0_m4m5_noshield", m=1):
        return Passive(
            name=name, model=model, w_um=5.0, l_um=5.0, multiplicity=m,
            plus=plus, minus=minus,
        )

    def _interconnect(self, passives):
        """An ``Interconnect`` with only the two attributes the chain check reads."""
        obj = Interconnect.__new__(Interconnect)
        obj.passives = passives
        obj.left_rail_x = {"a": -6.0, "e": -7.6}
        return obj

    def _chain(self, passives):
        return Interconnect._mim_series_chain(self._interconnect(passives))

    def test_valid_chain_returns_its_nodes(self):
        nodes = self._chain(
            [
                self._cap("C1", "a", "b"),
                self._cap("C2", "b", "c"),
                self._cap("C3", "c", "d"),
                self._cap("C4", "d", "e"),
            ]
        )
        self.assertEqual(nodes, ["a", "b", "c", "d", "e"])

    def test_broken_link_raises(self):
        with self.assertRaises(GenError):
            self._chain(
                [
                    self._cap("C1", "a", "b"),
                    self._cap("C2", "x", "c"),
                    self._cap("C3", "c", "d"),
                    self._cap("C4", "d", "e"),
                ]
            )

    def test_loop_raises(self):
        with self.assertRaises(GenError):
            self._chain(
                [
                    self._cap("C1", "a", "b"),
                    self._cap("C2", "b", "a"),
                    self._cap("C3", "a", "b"),
                    self._cap("C4", "b", "e"),
                ]
            )

    def test_odd_length_chain_raises(self):
        # Odd counts would leave one chain end on Metal5, which mim_caps()
        # does not draw an escape for -- it refuses rather than guessing.
        with self.assertRaises(GenError):
            self._chain([self._cap("C1", "a", "b"), self._cap("C2", "b", "e")][:1])

    def test_unknown_model_raises(self):
        with self.assertRaises(GenError):
            self._chain(
                [
                    self._cap("C1", "a", "b", model="cap_mim_1f0_m4m5_noshield"),
                    self._cap("C2", "b", "e"),
                ]
            )

    def test_endpoint_without_a_rail_raises(self):
        with self.assertRaises(GenError):
            self._chain([self._cap("C1", "a", "b"), self._cap("C2", "b", "nowhere")])


class MimReferenceCapacitanceTest(unittest.TestCase):
    """``make_reference.mim_capacitance_f`` restates the deck's two-term model.

    The LVS reference has to carry the *same* capacitance `klt extract`
    measures, because ``kdb.NetlistComparer`` compares a matched pair's
    parameters directly -- but it must get there by deriving from the
    schematic's own geometry, not by copying an extracted number back (which
    would make the compare circular).  These are hand-computed from the two
    published coefficients.
    """

    def test_five_by_five_plate(self):
        # 1.99e-15 F/um^2 * 25 um^2 + 2.383e-16 F/um * 20 um
        #   = 4.975e-14 + 4.766e-15 = 5.4516e-14 F
        self.assertAlmostEqual(
            mim_capacitance_f(5.0, 5.0), 5.4516e-14, delta=1e-19
        )

    def test_area_and_perimeter_terms_are_both_present(self):
        """A one-term (area-only) model would give 4.975e-14 -- 8.7% low."""
        self.assertGreater(mim_capacitance_f(5.0, 5.0), 1.99e-15 * 25.0)

    def test_committed_stack_is_about_twelve_femtofarads_in_series(self):
        """Four of these in series is decision record 0014's ~12-14 fF target."""
        single = mim_capacitance_f(5.0, 5.0)
        series = single / 4.0
        self.assertGreater(series, 12e-15)
        self.assertLess(series, 14e-15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
