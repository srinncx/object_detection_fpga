## =============================================================================
## constraints.xdc  —  Digilent Arty Z7-20 (Zynq XC7Z020-CLG400-1)
## Color detection accelerator
## =============================================================================
##
## Part number: xc7z020clg400-1
## Verified against Digilent Arty-Z7-20-Master.xdc
## (github.com/Digilent/digilent-xdc/Arty-Z7-20-Master.xdc)
##
## Signal    Package Pin   Schematic net   Notes
## -------   -----------   -------------   --------------------------------
## clk       H16           SYSCLK          125 MHz onboard oscillator
## rst       D19           BTN0            Button 0, active high
## rx        V6            JA[2] PMOD      Use JA PMOD pin for PL UART RX
## leds[0]   R14           LED0            LD0 green
## leds[1]   P14           LED1            LD1 green
## leds[2]   N16           LED2            LD2 green
##
## IMPORTANT — Clock frequency:
##   Arty Z7-20 system clock is 125 MHz (period = 8.000 ns), NOT 100 MHz.
##   uart_rx.v must be updated: change CLK_FREQ parameter from 100_000_000
##   to 125_000_000 so CLKS_PER_BIT = 125_000_000/9600 = 13020 (correct).
##   If CLK_FREQ stays at 100MHz on a 125MHz clock, UART will misread bytes.
##
## IMPORTANT — UART RX pin:
##   The Arty Z7-20 USB-UART bridge connects to the Zynq PS (ARM side),
##   NOT the PL (FPGA fabric). For pure PL designs you have two options:
##   Option A (recommended): Use PMOD JA pin 2 (V6) as UART RX.
##                           Connect USB-to-UART adapter: GND->GND, TX->V6.
##   Option B: Use the Zynq PS UART and route through AXI to PL (complex).
##   This constraints file uses Option A (PMOD JA pin 2).
##
## PMOD JA connector wiring for UART:
##   JA pin 1 (top-left)  = unused
##   JA pin 2             = V6  <- connect USB-UART adapter TX here
##   JA pin 5             = GND <- connect USB-UART adapter GND here

## ── Clock (125 MHz PL oscillator) ────────────────────────────────────────────
set_property PACKAGE_PIN H16      [get_ports clk]
set_property IOSTANDARD  LVCMOS33 [get_ports clk]
create_clock -period 8.000 -name sys_clk [get_ports clk]

## ── Reset (BTN0, active high) ─────────────────────────────────────────────────
set_property PACKAGE_PIN D19      [get_ports rst]
set_property IOSTANDARD  LVCMOS33 [get_ports rst]

## ── UART RX (PMOD JA pin 2) ───────────────────────────────────────────────────
set_property PACKAGE_PIN V6       [get_ports rx]
set_property IOSTANDARD  LVCMOS33 [get_ports rx]

## ── LEDs ──────────────────────────────────────────────────────────────────────
set_property PACKAGE_PIN R14      [get_ports {leds[0]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {leds[0]}]

set_property PACKAGE_PIN P14      [get_ports {leds[1]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {leds[1]}]

set_property PACKAGE_PIN N16      [get_ports {leds[2]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {leds[2]}]

## ── Timing constraints ────────────────────────────────────────────────────────
set_input_delay -clock sys_clk -max 0.000 [get_ports rst]
set_input_delay -clock sys_clk -min 0.000 [get_ports rst]
set_input_delay -clock sys_clk -max 0.000 [get_ports rx]
set_input_delay -clock sys_clk -min 0.000 [get_ports rx]

set_false_path -to [get_ports {leds[0]}]
set_false_path -to [get_ports {leds[1]}]
set_false_path -to [get_ports {leds[2]}]
