// packet_decoder.v
// ----------------
// Buffers 5 bytes from uart_rx and validates the packet format:
//
//   [0xAA] [R] [G] [B] [0x55]
//
// Ports:
//   clk        : system clock
//   rst        : synchronous active-high reset
//   byte_in    : byte from uart_rx data_out
//   byte_valid : strobe from uart_rx data_valid (1 clock pulse)
//   r_out      : red   channel (8-bit)
//   g_out      : green channel (8-bit)
//   b_out      : blue  channel (8-bit)
//   pkt_done   : pulses HIGH 1 clock when valid packet received
//   pkt_error  : pulses HIGH 1 clock on framing error (wrong start/end byte)
//
// Operation:
//   State machine waits for 0xAA, then collects R, G, B, then checks 0x55.
//   On success: latches RGB, pulses pkt_done.
//   On error  : resets and pulses pkt_error. If the bad byte is 0xAA it
//               immediately re-enters the R state (handles re-sync).

module packet_decoder (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] byte_in,
    input  wire       byte_valid,
    output reg  [7:0] r_out,
    output reg  [7:0] g_out,
    output reg  [7:0] b_out,
    output reg        pkt_done,
    output reg        pkt_error
);

// ── FSM states ────────────────────────────────────────────────────────────────
localparam WAIT_START = 3'd0;
localparam RECV_R     = 3'd1;
localparam RECV_G     = 3'd2;
localparam RECV_B     = 3'd3;
localparam RECV_END   = 3'd4;

localparam START_BYTE = 8'hAA;
localparam END_BYTE   = 8'h55;

// ── Internal ──────────────────────────────────────────────────────────────────
reg [2:0] state;
reg [7:0] r_buf, g_buf, b_buf;

always @(posedge clk) begin
    if (rst) begin
        state     <= WAIT_START;
        r_buf     <= 0;
        g_buf     <= 0;
        b_buf     <= 0;
        r_out     <= 0;
        g_out     <= 0;
        b_out     <= 0;
        pkt_done  <= 0;
        pkt_error <= 0;
    end else begin
        // Default: clear strobes every cycle
        pkt_done  <= 0;
        pkt_error <= 0;

        if (byte_valid) begin
            case (state)

                // ── Wait for 0xAA start byte ──────────────────────────────────
                WAIT_START: begin
                    if (byte_in == START_BYTE)
                        state <= RECV_R;
                    // any other byte: stay in WAIT_START silently
                end

                // ── Receive R ─────────────────────────────────────────────────
                RECV_R: begin
                    if (byte_in == START_BYTE) begin
                        // Another start byte — resync, stay in RECV_R
                        state <= RECV_R;
                    end else begin
                        r_buf <= byte_in;
                        state <= RECV_G;
                    end
                end

                // ── Receive G ─────────────────────────────────────────────────
                RECV_G: begin
                    if (byte_in == START_BYTE) begin
                        pkt_error <= 1;
                        state     <= RECV_R;   // resync
                    end else begin
                        g_buf <= byte_in;
                        state <= RECV_B;
                    end
                end

                // ── Receive B ─────────────────────────────────────────────────
                RECV_B: begin
                    if (byte_in == START_BYTE) begin
                        pkt_error <= 1;
                        state     <= RECV_R;   // resync
                    end else begin
                        b_buf <= byte_in;
                        state <= RECV_END;
                    end
                end

                // ── Check end byte 0x55 ───────────────────────────────────────
                RECV_END: begin
                    if (byte_in == END_BYTE) begin
                        // Valid packet — latch outputs
                        r_out    <= r_buf;
                        g_out    <= g_buf;
                        b_out    <= b_buf;
                        pkt_done <= 1;
                        state    <= WAIT_START;
                    end else if (byte_in == START_BYTE) begin
                        // Immediate resync on new start byte
                        pkt_error <= 1;
                        state     <= RECV_R;
                    end else begin
                        pkt_error <= 1;
                        state     <= WAIT_START;
                    end
                end

                default: state <= WAIT_START;

            endcase
        end
    end
end

endmodule
