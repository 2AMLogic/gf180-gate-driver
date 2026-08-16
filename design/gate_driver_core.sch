v {xschem version=3.4.7 file_version=1.2

* gate_driver_core -- top-level low-side gate-driver block (issue #98)
*
* Instantiates the two existing sub-cells as a single block:
*   x1  level_shifter  design/level_shifter.sch  (spec/gate-driver.md Sec.4)
*   x2  output_stage   design/output_stage.sch   (spec/gate-driver.md Sec.3)
*
* Both sub-cell symbols are referenced bare (`level_shifter.sym`,
* `output_stage.sym`) and live next to their own `.sch` under design/, so
* xschem descends into them and emits real `.subckt` bodies rather than
* empty stubs -- see design/README.md's hierarchical-symbol note.
*
* Signal path (spec/decision-records/0001 Decision 3: non-inverting,
* IN high -> OUT drives the external switch on):
*   IN (3.3V logic, GND_LOGIC-referenced)
*     -> x1 level_shifter  (thin-oxide input pair, thick-oxide cascode +
*        drive-rail latch + 2-inverter drive-rail buffer; non-inverting)
*     -> IN_DRV (drive-rail-referenced logic, the internal net between the
*        two sub-cells; this is output_stage's "IN_DRV" port, NOT the
*        block's 3.3V IN pin)
*     -> x2 output_stage   (5-stage thick-oxide tapered pre-driver + push-
*        pull final stage, 6 inversions = non-inverting)
*     -> OUT (gate drive into the 1 nF reference load, spec Sec.3)
*
* Block ports -- exactly spec/decision-records/0001 Decision 1's port
* table, no more and no less:
*   VDD_LOGIC -- 3.3V logic supply         (x1 only)
*   GND_LOGIC -- 3.3V logic return         (x1 only)
*   IN        -- 3.3V logic input          (x1 only)
*   VDD_DRV   -- 5V/6V drive rail          (x1 and x2)
*   GND_DRV   -- drive-rail return         (x1 and x2)
*   OUT       -- gate-drive output         (x2 only)
* The ipin/opin instances below are placed in that table's order, but the
* .subckt port ORDER in the derived netlist is taken from
* gate_driver_core.sym's pin (B-line) order, which make_sym.awk groups
* inputs-then-output-then-remaining-inputs:
*   VDD_LOGIC GND_LOGIC IN OUT VDD_DRV GND_DRV
* Connect by name, not by position, when instantiating this cell.
*
* GND_LOGIC and GND_DRV are two pins but one electrical reference node by
* design intent (decision record 0001, Decision 1) -- they are deliberately
* kept as two separate top-level ports here and must be tied together in
* any testbench that instantiates this cell.
*
* NOT in this cell yet: UVLO (spec Sec.5 / decision record 0001 Decisions
* 4-5) is in scope for this increment but has no implemented sub-cell to
* instantiate. This top cell is the level-shifter + output-stage signal
* path only; the UVLO comparator and its OUT pull-down are a separate
* sub-cell to be added here when they exist.
}
G {}
K {}
V {}
S {}
E {}
C {level_shifter.sym} 0 0 0 0 {name=x1}
C {devices/lab_pin.sym} -30 0 0 0 {name=l1 lab=IN}
C {devices/lab_pin.sym} -10 -50 0 0 {name=l2 lab=VDD_LOGIC}
C {devices/lab_pin.sym} 10 -50 0 0 {name=l3 lab=GND_LOGIC}
C {devices/lab_pin.sym} -10 50 0 0 {name=l4 lab=VDD_DRV}
C {devices/lab_pin.sym} 10 50 0 0 {name=l5 lab=GND_DRV}
C {devices/lab_pin.sym} 30 0 0 0 {name=l6 lab=IN_DRV}
C {output_stage.sym} 400 0 0 0 {name=x2}
C {devices/lab_pin.sym} 100 -20 0 0 {name=l7 lab=VDD_DRV}
C {devices/lab_pin.sym} 100 0 0 0 {name=l8 lab=IN_DRV}
C {devices/lab_pin.sym} 100 20 0 0 {name=l9 lab=GND_DRV}
C {devices/lab_pin.sym} 700 -20 0 0 {name=l10 lab=OUT}
C {devices/ipin.sym} -200 -150 0 0 {name=p_vddl lab=VDD_LOGIC}
C {devices/ipin.sym} -200 -100 0 0 {name=p_gndl lab=GND_LOGIC}
C {devices/ipin.sym} -200 -50 0 0 {name=p_in lab=IN}
C {devices/ipin.sym} -200 0 0 0 {name=p_vddd lab=VDD_DRV}
C {devices/ipin.sym} -200 50 0 0 {name=p_gndd lab=GND_DRV}
C {devices/opin.sym} 900 -20 0 0 {name=p_out lab=OUT}
