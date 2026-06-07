// uart_rx.v
// ---------
// 9600 baud UART receiver, 8N1, 100 MHz system clock
//
// Parameters:
//   CLK_FREQ  : system clock frequency in Hz (default 100 MHz)
//   BAUD_RATE : baud rate (default 9600)
//
// Ports:
//   clk      : system clock
//   rst      : synchronous active-high reset
//   rx       : UART RX line (connect to FPGA pin)
//   data_out : received byte
//   data_valid: pulses HIGH for 1 clock cycle when data_out is valid
//
// Operation:
//   1. Detects falling edge on rx (start bit)
//   2. Waits 1.5 bit periods to sample centre of bit 0
//   3. Samples 8 data bits, each 1 bit period apart
//   4. Checks stop bit, pulses data_valid if stop bit is HIGH
//
// Timing (100 MHz, 9600 baud):
//   CLKS_PER_BIT = 100_000_000 / 9600 = 10416
//   Half bit     = 5208 clocks  (used to align to centre)

module uart_rx #(
    parameter CLK_FREQ  = 100_000_000,
    parameter BAUD_RATE = 9600
)(
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,
    output reg  [7:0] data_out,
    output reg        data_valid
);

// ── Timing ────────────────────────────────────────────────────────────────────
localparam CLKS_PER_BIT  = CLK_FREQ / BAUD_RATE;        // 10416
localparam HALF_BIT      = CLKS_PER_BIT / 2;            // 5208

// ── FSM states ────────────────────────────────────────────────────────────────
localparam IDLE      = 3'd0;
localparam START_BIT = 3'd1;
localparam DATA_BITS = 3'd2;
localparam STOP_BIT  = 3'd3;
localparam DONE      = 3'd4;

// ── Internal signals ──────────────────────────────────────────────────────────
reg [2:0]  state;
reg [13:0] clk_count;    // counts up to CLKS_PER_BIT (needs 14 bits for 10416)
reg [2:0]  bit_index;    // 0-7, which data bit we are receiving
reg [7:0]  rx_shift;     // shift register for incoming bits

// ── Double-flop rx for metastability ─────────────────────────────────────────
reg rx_d1, rx_d2;
always @(posedge clk) begin
    rx_d1 <= rx;
    rx_d2 <= rx_d1;
end

// ── FSM ───────────────────────────────────────────────────────────────────────
always @(posedge clk) begin
    if (rst) begin
        state      <= IDLE;
        clk_count  <= 0;
        bit_index  <= 0;
        rx_shift   <= 0;
        data_out   <= 0;
        data_valid <= 0;
    end else begin
        data_valid <= 0;   // default: no valid pulse

        case (state)

            // ── Wait for falling edge (start bit) ────────────────────────────
            IDLE: begin
                clk_count <= 0;
                bit_index <= 0;
                if (rx_d2 == 1'b0)          // start bit detected
                    state <= START_BIT;
            end

            // ── Wait half a bit period to centre on start bit ─────────────────
            START_BIT: begin
                if (clk_count == HALF_BIT - 1) begin
                    if (rx_d2 == 1'b0) begin   // still low: valid start
                        clk_count <= 0;
                        state     <= DATA_BITS;
                    end else begin              // glitch: go back to idle
                        state <= IDLE;
                    end
                end else begin
                    clk_count <= clk_count + 1;
                end
            end

            // ── Sample 8 data bits ────────────────────────────────────────────
            DATA_BITS: begin
                if (clk_count == CLKS_PER_BIT - 1) begin
                    clk_count          <= 0;
                    rx_shift[bit_index] <= rx_d2;   // LSB first
                    if (bit_index == 3'd7) begin
                        bit_index <= 0;
                        state     <= STOP_BIT;
                    end else begin
                        bit_index <= bit_index + 1;
                    end
                end else begin
                    clk_count <= clk_count + 1;
                end
            end

            // ── Verify stop bit (must be HIGH) ───────────────────────────────
            STOP_BIT: begin
                if (clk_count == CLKS_PER_BIT - 1) begin
                    clk_count <= 0;
                    if (rx_d2 == 1'b1) begin   // valid stop bit
                        data_out   <= rx_shift;
                        state      <= DONE;
                    end else begin             // framing error — discard
                        state <= IDLE;
                    end
                end else begin
                    clk_count <= clk_count + 1;
                end
            end

            // ── Pulse data_valid for one clock ───────────────────────────────
            DONE: begin
                data_valid <= 1'b1;
                state      <= IDLE;
            end

            default: state <= IDLE;

        endcase
    end
end

endmodule
