## =============================================================================
## constraints.xdc  —  Basys3 (Artix-7 XC7A35T)
## Color detection accelerator
## =============================================================================
##
## FIX HISTORY:
##   v1: missing output constraints       -> no_output_delay HIGH
##   v2: set_false_path + set_max_delay   -> partial_input_delay conflict
##   v3: set_input/output_delay = 0       -> output OBUF clock skew -5.159ns
##       Vivado subtracts 5.159ns clock skew from 10ns budget leaving only
##       4.841ns for FF->OBUF->pad path (5.515ns actual) = -0.710ns violation
##   v4 (this): set_false_path on OUTPUTS removes them from timing analysis
##              entirely — no clock skew calculation, no violation.
##              set_input_delay=0 on inputs (cleared no_input_delay DRC).
##              This is the correct approach for asynchronous LED outputs.
##
## WHY set_false_path for outputs but set_input_delay for inputs:
##   Outputs: LED pins have no external clock relationship at all.
##            set_false_path removes them from ALL timing analysis.
##            set_output_delay=0 keeps them in analysis and Vivado applies
##            the internal clock network skew (~5ns) as a penalty.
##   Inputs:  set_input_delay=0 properly constrains rst/rx as synchronous
##            inputs with 0ns external delay, clearing DRC without conflicts.

## ── Clock ─────────────────────────────────────────────────────────────────────
set_property PACKAGE_PIN W5       [get_ports clk]
set_property IOSTANDARD  LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk [get_ports clk]

## ── Reset ─────────────────────────────────────────────────────────────────────
set_property PACKAGE_PIN T18      [get_ports rst]
set_property IOSTANDARD  LVCMOS33 [get_ports rst]

## ── UART RX ───────────────────────────────────────────────────────────────────
set_property PACKAGE_PIN B18      [get_ports rx]
set_property IOSTANDARD  LVCMOS33 [get_ports rx]

## ── LEDs ──────────────────────────────────────────────────────────────────────
set_property PACKAGE_PIN U16      [get_ports {leds[0]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {leds[0]}]

set_property PACKAGE_PIN E19      [get_ports {leds[1]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {leds[1]}]

set_property PACKAGE_PIN U19      [get_ports {leds[2]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {leds[2]}]

## ── Timing constraints ────────────────────────────────────────────────────────

## INPUTS: set_input_delay=0 (clears no_input_delay DRC, no conflict)
## rst and rx are asynchronous — double-flopped inside uart_rx
set_input_delay -clock sys_clk -max 0.000 [get_ports rst]
set_input_delay -clock sys_clk -min 0.000 [get_ports rst]
set_input_delay -clock sys_clk -max 0.000 [get_ports rx]
set_input_delay -clock sys_clk -min 0.000 [get_ports rx]

## OUTPUTS: set_false_path (removes from timing analysis completely)
## LEDs are visual indicators with no external clock relationship.
## set_output_delay=0 causes Vivado to apply internal clock skew (~5ns)
## as a penalty making the path appear to violate. set_false_path avoids this.
set_false_path -to [get_ports {leds[0]}]
set_false_path -to [get_ports {leds[1]}]
set_false_path -to [get_ports {leds[2]}]

## =============================================================================
## ZedBoard (Zynq XC7Z020) — uncomment and comment Basys3 section above
## =============================================================================

# set_property PACKAGE_PIN Y9       [get_ports clk]
# set_property IOSTANDARD  LVCMOS33 [get_ports clk]
# create_clock -period 10.000 -name sys_clk [get_ports clk]
# set_property PACKAGE_PIN P16      [get_ports rst]
# set_property IOSTANDARD  LVCMOS18 [get_ports rst]
# set_property PACKAGE_PIN V12      [get_ports rx]
# set_property IOSTANDARD  LVCMOS33 [get_ports rx]
# set_property PACKAGE_PIN T22      [get_ports {leds[0]}]
# set_property IOSTANDARD  LVCMOS33 [get_ports {leds[0]}]
# set_property PACKAGE_PIN T21      [get_ports {leds[1]}]
# set_property IOSTANDARD  LVCMOS33 [get_ports {leds[1]}]
# set_property PACKAGE_PIN U22      [get_ports {leds[2]}]
# set_property IOSTANDARD  LVCMOS33 [get_ports {leds[2]}]
# set_input_delay -clock sys_clk -max 0.000 [get_ports rst]
# set_input_delay -clock sys_clk -min 0.000 [get_ports rst]
# set_input_delay -clock sys_clk -max 0.000 [get_ports rx]
# set_input_delay -clock sys_clk -min 0.000 [get_ports rx]
# set_false_path -to [get_ports {leds[0]}]
# set_false_path -to [get_ports {leds[1]}]
# set_false_path -to [get_ports {leds[2]}]
