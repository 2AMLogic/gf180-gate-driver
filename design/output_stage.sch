v {xschem version=3.4.7 file_version=1.2

* output_stage -- low-side gate-driver output stage (issue #6)
*
* Thick-oxide (nfet_06v0/pfet_06v0) 5-stage tapered pre-driver
* (stages 1-5) driving a complementary push-pull final stage
* (stage 6) into the 1 nF reference load (spec/gate-driver.md
* Sec.3). Every device in this cell is nfet_06v0/pfet_06v0 --
* spec Sec.2.5. Sizing derivation: design/output-stage-sizing.md.
*
* Ports (thick-oxide/drive-rail domain only -- see
* spec/decision-records/0001-block-interface-and-uvlo-parameters.md
* Decision 1 for the block-level port list this cell's ports are
* drawn from):
*   IN_DRV  -- drive-rail-referenced logic input (from the level
*              shifter, issue #7 -- NOT the block's 3.3V IN pin)
*   VDD_DRV -- 5V nominal / 6V stretch drive rail (block VDD_DRV)
*   GND_DRV -- drive rail return (block GND_DRV)
*   OUT     -- gate-drive output into the 1 nF reference load
*              (block OUT)
}
G {}
K {}
V {}
S {}
E {}
C {symbols/pfet_06v0.sym} 0 -150 0 0 {name=MP1
L=0.55u
W=4.4u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 20 -120 0 0 {name=l1 lab=n1}
C {devices/ipin.sym} -20 -150 0 0 {name=l2 lab=IN_DRV}
C {devices/ipin.sym} 20 -180 0 0 {name=l3 lab=VDD_DRV}
C {devices/lab_pin.sym} 20 -150 0 0 {name=l4 lab=VDD_DRV}
C {symbols/nfet_06v0.sym} 0 150 0 0 {name=MN1
L=0.70u
W=2.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 20 120 0 0 {name=l5 lab=n1}
C {devices/lab_pin.sym} -20 150 0 0 {name=l6 lab=IN_DRV}
C {devices/ipin.sym} 20 180 0 0 {name=l7 lab=GND_DRV}
C {devices/lab_pin.sym} 20 150 0 0 {name=l8 lab=GND_DRV}
C {symbols/pfet_06v0.sym} 300 -150 0 0 {name=MP2
L=0.55u
W=18.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 320 -120 0 0 {name=l9 lab=n2}
C {devices/lab_pin.sym} 280 -150 0 0 {name=l10 lab=n1}
C {devices/lab_pin.sym} 320 -180 0 0 {name=l11 lab=VDD_DRV}
C {devices/lab_pin.sym} 320 -150 0 0 {name=l12 lab=VDD_DRV}
C {symbols/nfet_06v0.sym} 300 150 0 0 {name=MN2
L=0.70u
W=8.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 320 120 0 0 {name=l13 lab=n2}
C {devices/lab_pin.sym} 280 150 0 0 {name=l14 lab=n1}
C {devices/lab_pin.sym} 320 180 0 0 {name=l15 lab=GND_DRV}
C {devices/lab_pin.sym} 320 150 0 0 {name=l16 lab=GND_DRV}
C {symbols/pfet_06v0.sym} 600 -150 0 0 {name=MP3
L=0.55u
W=73.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 620 -120 0 0 {name=l17 lab=n3}
C {devices/lab_pin.sym} 580 -150 0 0 {name=l18 lab=n2}
C {devices/lab_pin.sym} 620 -180 0 0 {name=l19 lab=VDD_DRV}
C {devices/lab_pin.sym} 620 -150 0 0 {name=l20 lab=VDD_DRV}
C {symbols/nfet_06v0.sym} 600 150 0 0 {name=MN3
L=0.70u
W=33.0u
nf=1
m=1
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 620 120 0 0 {name=l21 lab=n3}
C {devices/lab_pin.sym} 580 150 0 0 {name=l22 lab=n2}
C {devices/lab_pin.sym} 620 180 0 0 {name=l23 lab=GND_DRV}
C {devices/lab_pin.sym} 620 150 0 0 {name=l24 lab=GND_DRV}
C {symbols/pfet_06v0.sym} 900 -150 0 0 {name=MP4
L=0.55u
W=10.0u
nf=1
m=30
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 920 -120 0 0 {name=l25 lab=n4}
C {devices/lab_pin.sym} 880 -150 0 0 {name=l26 lab=n3}
C {devices/lab_pin.sym} 920 -180 0 0 {name=l27 lab=VDD_DRV}
C {devices/lab_pin.sym} 920 -150 0 0 {name=l28 lab=VDD_DRV}
C {symbols/nfet_06v0.sym} 900 150 0 0 {name=MN4
L=0.70u
W=10.0u
nf=1
m=14
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 920 120 0 0 {name=l29 lab=n4}
C {devices/lab_pin.sym} 880 150 0 0 {name=l30 lab=n3}
C {devices/lab_pin.sym} 920 180 0 0 {name=l31 lab=GND_DRV}
C {devices/lab_pin.sym} 920 150 0 0 {name=l32 lab=GND_DRV}
C {symbols/pfet_06v0.sym} 1200 -150 0 0 {name=MP5
L=0.55u
W=10.0u
nf=1
m=122
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 -120 0 0 {name=l33 lab=n5}
C {devices/lab_pin.sym} 1180 -150 0 0 {name=l34 lab=n4}
C {devices/lab_pin.sym} 1220 -180 0 0 {name=l35 lab=VDD_DRV}
C {devices/lab_pin.sym} 1220 -150 0 0 {name=l36 lab=VDD_DRV}
C {symbols/nfet_06v0.sym} 1200 150 0 0 {name=MN5
L=0.70u
W=10.0u
nf=1
m=55
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 120 0 0 {name=l37 lab=n5}
C {devices/lab_pin.sym} 1180 150 0 0 {name=l38 lab=n4}
C {devices/lab_pin.sym} 1220 180 0 0 {name=l39 lab=GND_DRV}
C {devices/lab_pin.sym} 1220 150 0 0 {name=l40 lab=GND_DRV}
C {symbols/pfet_06v0.sym} 1500 -150 0 0 {name=MP6
L=0.55u
W=10.0u
nf=1
m=500
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 1520 -120 0 0 {name=l41 lab=OUT}
C {devices/lab_pin.sym} 1480 -150 0 0 {name=l42 lab=n5}
C {devices/lab_pin.sym} 1520 -180 0 0 {name=l43 lab=VDD_DRV}
C {devices/lab_pin.sym} 1520 -150 0 0 {name=l44 lab=VDD_DRV}
C {symbols/nfet_06v0.sym} 1500 150 0 0 {name=MN6
L=0.70u
W=10.0u
nf=1
m=220
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X
}
C {devices/opin.sym} 1520 120 0 0 {name=l45 lab=OUT}
C {devices/lab_pin.sym} 1480 150 0 0 {name=l46 lab=n5}
C {devices/lab_pin.sym} 1520 180 0 0 {name=l47 lab=GND_DRV}
C {devices/lab_pin.sym} 1520 150 0 0 {name=l48 lab=GND_DRV}

