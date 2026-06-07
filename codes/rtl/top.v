// led_output.v
// ------------
// Maps 3-bit class index to 3 LEDs on Basys3 / ZedBoard.
//
// LED encoding (matches COLOR_NAMES in Python):
//   000 = yellow
//   001 = orange
//   010 = red
//   011 = violet
//   100 = blue
//   101 = green
//   110 = white
//   111 = black
//
// LEDs update only when we pulse valid HIGH.
// Between packets the last prediction stays latched.

module led_output (
    input  wire       clk,
    input  wire       rst,
    input  wire [2:0] class_idx,
    input  wire       valid,       // connect to mlp_core done
    output reg  [2:0] leds         // connect to LED[2:0] on board
);

always @(posedge clk) begin
    if (rst)
        leds <= 3'b000;
    else if (valid)
        leds <= class_idx;
end

endmodule


// =============================================================================
// top.v
// -----
// Top-level module. Wires uart_rx -> packet_decoder -> mlp_core -> led_output.
//
// Pin mapping (see basys3.xdc / zedboard.xdc):
//   clk   : 100 MHz system clock
//   rst   : active-high reset (mapped to a button)
//   rx    : UART RX pin
//   leds  : LED[2:0]
// =============================================================================

module top (
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,
    output wire [2:0] leds
);

// ── uart_rx -> packet_decoder wires ──────────────────────────────────────────
wire [7:0] uart_byte;
wire       uart_valid;

// ── packet_decoder -> mlp_core wires ─────────────────────────────────────────
wire [7:0] r_wire, g_wire, b_wire;
wire       pkt_done;
wire       pkt_error;   // unused in hardware, useful in simulation

// ── mlp_core -> led_output wires ─────────────────────────────────────────────
wire [2:0] class_idx;
wire       mlp_done;

// ── Instantiate uart_rx ───────────────────────────────────────────────────────
uart_rx #(
    .CLK_FREQ  (100_000_000),
    .BAUD_RATE (9600)
) u_uart_rx (
    .clk        (clk),
    .rst        (rst),
    .rx         (rx),
    .data_out   (uart_byte),
    .data_valid (uart_valid)
);

// ── Instantiate packet_decoder ────────────────────────────────────────────────
packet_decoder u_pkt_dec (
    .clk        (clk),
    .rst        (rst),
    .byte_in    (uart_byte),
    .byte_valid (uart_valid),
    .r_out      (r_wire),
    .g_out      (g_wire),
    .b_out      (b_wire),
    .pkt_done   (pkt_done),
    .pkt_error  (pkt_error)
);

// ── Instantiate mlp_core ──────────────────────────────────────────────────────
mlp_core u_mlp (
    .clk    (clk),
    .rst    (rst),
    .start  (pkt_done),
    .r_in   (r_wire),
    .g_in   (g_wire),
    .b_in   (b_wire),
    .result (class_idx),
    .done   (mlp_done)
);

// ── Instantiate led_output ────────────────────────────────────────────────────
led_output u_leds (
    .clk       (clk),
    .rst       (rst),
    .class_idx (class_idx),
    .valid     (mlp_done),
    .leds      (leds)
);

endmodule
