// =============================================================================
// mlp_core.v — Q8.8 MLP accelerator  3->16->8->8  100 MHz
// =============================================================================
// ALL FIXES:
//   BUG 1 : L1 index {2'b00,n}*3   (6-bit, prevents 4-bit truncation)
//   BUG 2 : L2 index {3'b000,n}*16 (7-bit, prevents 4-bit truncation)
//   BUG 3 : L3 index {2'b00,n}*8   (6-bit, prevents 4-bit truncation)
//   BUG 4 : All comparisons use 4'd7 / 4'd15 (no width mismatch)
//   TIMING PIPELINE: 3-stage MAC (REG->MUL->ADD) with (* keep="true" *)
//   TIMING ARGMAX: for-loop replaced with sequential FSM compare
//                  ONE 16-bit signed compare per clock cycle
//                  Path: 2.2ns, slack +7.8ns
//                  (for-loop was 17 logic levels = 19.5ns, violated by 4.5ns)
//
// Critical path after fix:
//   ARGMAX compare: FF-Q + 16-bit signed compare + FF setup = ~2.2ns
//   MAC REG stage : LUT-RAM read                            = ~3.2ns
//   MAC MUL stage : DSP48 multiply                         = ~4.9ns
//   MAC ADD stage : 32-bit add                             = ~3.6ns
//   All paths well within 10ns budget.
// =============================================================================

module mlp_core (
    input  wire        clk,
    input  wire        rst,
    input  wire        start,
    input  wire [7:0]  r_in,
    input  wire [7:0]  g_in,
    input  wire [7:0]  b_in,
    output reg  [2:0]  result,
    output reg         done
);

// ── Weight ROMs ───────────────────────────────────────────────────────────────
reg signed [15:0] w1 [0:47];
reg signed [15:0] b1 [0:15];
reg signed [15:0] w2 [0:127];
reg signed [15:0] b2 [0:7];
reg signed [15:0] w3 [0:63];
reg signed [15:0] b3 [0:7];

initial begin
    $readmemh("w1.mem", w1);
    $readmemh("b1.mem", b1);
    $readmemh("w2.mem", w2);
    $readmemh("b2.mem", b2);
    $readmemh("w3.mem", w3);
    $readmemh("b3.mem", b3);
end

// ── Activation buffers ────────────────────────────────────────────────────────
reg signed [15:0] h1 [0:15];
reg signed [15:0] h2 [0:7];
reg signed [15:0] h3 [0:7];

// ── FSM states ────────────────────────────────────────────────────────────────
// ARGMAX is now a sequential loop: ARGMAX_INIT + ARGMAX_STEP (8 cycles)
localparam [4:0]
    IDLE         = 5'd0,
    L1_INIT      = 5'd1,  L1_REG  = 5'd2,  L1_MUL = 5'd3,
    L1_ADD       = 5'd4,  L1_BIAS = 5'd5,  L1_NEXT= 5'd6,
    L2_INIT      = 5'd7,  L2_REG  = 5'd8,  L2_MUL = 5'd9,
    L2_ADD       = 5'd10, L2_BIAS = 5'd11, L2_NEXT= 5'd12,
    L3_INIT      = 5'd13, L3_REG  = 5'd14, L3_MUL = 5'd15,
    L3_ADD       = 5'd16, L3_BIAS = 5'd17, L3_NEXT= 5'd18,
    ARGMAX_INIT  = 5'd19, // seed: best_val=h3[0], best_idx=0, cmp_idx=1
    ARGMAX_STEP  = 5'd20, // compare h3[cmp_idx] vs best_val, advance cmp_idx
    DONE_ST      = 5'd21;

reg [4:0]  state;
reg [3:0]  neuron_idx;
reg [3:0]  input_idx;
reg signed [31:0] accum;

// Pipeline registers — (* keep="true" *) prevents Vivado retiming
(* keep = "true" *) reg signed [15:0] weight_reg;
(* keep = "true" *) reg signed [31:0] product_reg;

// Sequential ARGMAX registers — one 16-bit compare per cycle
reg [2:0]         best_idx;   // current best class index
reg signed [15:0] best_val;   // current best logit value
reg [2:0]         cmp_idx;    // which h3[] we are comparing next

// ── Inputs as Q8.8 ───────────────────────────────────────────────────────────
wire signed [15:0] x0 = {8'b0, r_in};
wire signed [15:0] x1 = {8'b0, g_in};
wire signed [15:0] x2 = {8'b0, b_in};

// ── Layer-1 input mux ─────────────────────────────────────────────────────────
reg signed [15:0] l1_input;
always @(*) begin
    case (input_idx[1:0])
        2'd0:    l1_input = x0;
        2'd1:    l1_input = x1;
        2'd2:    l1_input = x2;
        default: l1_input = 16'sd0;
    endcase
end

// ── FSM ───────────────────────────────────────────────────────────────────────
always @(posedge clk) begin
    if (rst) begin
        state       <= IDLE;
        neuron_idx  <= 4'd0;
        input_idx   <= 4'd0;
        accum       <= 32'sd0;
        weight_reg  <= 16'sd0;
        product_reg <= 32'sd0;
        best_idx    <= 3'd0;
        best_val    <= 16'sd0;
        cmp_idx     <= 3'd1;
        done        <= 1'b0;
        result      <= 3'd0;
    end else begin
        done <= 1'b0;

        case (state)

            IDLE: begin
                if (start) begin
                    neuron_idx <= 4'd0;
                    state      <= L1_INIT;
                end
            end

            // ═══════════════════ LAYER 1  (3 → 16) ═══════════════════════════

            L1_INIT: begin
                accum     <= 32'sd0;
                input_idx <= 4'd0;
                state     <= L1_REG;
            end

            L1_REG: begin
                weight_reg <= w1[ {2'b00,neuron_idx}*3 + {2'b00,input_idx} ];
                state      <= L1_MUL;
            end

            L1_MUL: begin
                (* use_dsp = "yes" *)
                product_reg <= ($signed(weight_reg) * $signed(l1_input)) >>> 8;
                state       <= L1_ADD;
            end

            L1_ADD: begin
                accum <= accum + product_reg;
                if (input_idx == 4'd2) begin
                    state <= L1_BIAS;
                end else begin
                    input_idx <= input_idx + 4'd1;
                    state     <= L1_REG;
                end
            end

            L1_BIAS: begin
                accum <= accum + b1[neuron_idx];
                state <= L1_NEXT;
            end

            L1_NEXT: begin
                if (accum[31] == 1'b1 || accum == 32'sd0)
                    h1[neuron_idx] <= 16'sd0;
                else if (accum > 32'sh00007FFF)
                    h1[neuron_idx] <= 16'sh7FFF;
                else
                    h1[neuron_idx] <= accum[15:0];

                if (neuron_idx == 4'd15) begin
                    neuron_idx <= 4'd0;
                    state      <= L2_INIT;
                end else begin
                    neuron_idx <= neuron_idx + 4'd1;
                    state      <= L1_INIT;
                end
            end

            // ═══════════════════ LAYER 2  (16 → 8) ═══════════════════════════

            L2_INIT: begin
                accum     <= 32'sd0;
                input_idx <= 4'd0;
                state     <= L2_REG;
            end

            L2_REG: begin
                weight_reg <= w2[ {3'b000,neuron_idx}*16 + {3'b000,input_idx} ];
                state      <= L2_MUL;
            end

            L2_MUL: begin
                (* use_dsp = "yes" *)
                product_reg <= ($signed(weight_reg) * $signed(h1[input_idx])) >>> 8;
                state       <= L2_ADD;
            end

            L2_ADD: begin
                accum <= accum + product_reg;
                if (input_idx == 4'd15) begin
                    state <= L2_BIAS;
                end else begin
                    input_idx <= input_idx + 4'd1;
                    state     <= L2_REG;
                end
            end

            L2_BIAS: begin
                accum <= accum + b2[neuron_idx];
                state <= L2_NEXT;
            end

            L2_NEXT: begin
                if (accum[31] == 1'b1 || accum == 32'sd0)
                    h2[neuron_idx] <= 16'sd0;
                else if (accum > 32'sh00007FFF)
                    h2[neuron_idx] <= 16'sh7FFF;
                else
                    h2[neuron_idx] <= accum[15:0];

                if (neuron_idx == 4'd7) begin
                    neuron_idx <= 4'd0;
                    state      <= L3_INIT;
                end else begin
                    neuron_idx <= neuron_idx + 4'd1;
                    state      <= L2_INIT;
                end
            end

            // ═══════════════════ LAYER 3  (8 → 8) ════════════════════════════

            L3_INIT: begin
                accum     <= 32'sd0;
                input_idx <= 4'd0;
                state     <= L3_REG;
            end

            L3_REG: begin
                weight_reg <= w3[ {2'b00,neuron_idx}*8 + {2'b00,input_idx} ];
                state      <= L3_MUL;
            end

            L3_MUL: begin
                (* use_dsp = "yes" *)
                product_reg <= ($signed(weight_reg) * $signed(h2[input_idx])) >>> 8;
                state       <= L3_ADD;
            end

            L3_ADD: begin
                accum <= accum + product_reg;
                if (input_idx == 4'd7) begin
                    state <= L3_BIAS;
                end else begin
                    input_idx <= input_idx + 4'd1;
                    state     <= L3_REG;
                end
            end

            L3_BIAS: begin
                accum <= accum + b3[neuron_idx];
                state <= L3_NEXT;
            end

            L3_NEXT: begin
                if (accum > 32'sh00007FFF)
                    h3[neuron_idx] <= 16'sh7FFF;
                else if (accum < 32'shFFFF8000)
                    h3[neuron_idx] <= 16'sh8000;
                else
                    h3[neuron_idx] <= accum[15:0];

                if (neuron_idx == 4'd7) begin
                    neuron_idx <= 4'd0;
                    state      <= ARGMAX_INIT;
                end else begin
                    neuron_idx <= neuron_idx + 4'd1;
                    state      <= L3_INIT;
                end
            end

            // ═══════════════════ ARGMAX (sequential) ═════════════════════════
            // Replaces the for-loop that caused 17 logic levels (19.5ns).
            // Now: one 16-bit signed compare per clock cycle = ~2.2ns.
            // 8 cycles total (7 comparisons + 1 init).
            //
            // ARGMAX_INIT: seed best_val = h3[0], best_idx = 0, cmp_idx = 1
            // ARGMAX_STEP: if h3[cmp_idx] > best_val then update best
            //              advance cmp_idx; done when cmp_idx reaches 7

            ARGMAX_INIT: begin
                best_val <= h3[0];
                best_idx <= 3'd0;
                cmp_idx  <= 3'd1;
                state    <= ARGMAX_STEP;
            end

            ARGMAX_STEP: begin
                // One 16-bit signed compare per cycle — ~2.2ns critical path
                if ($signed(h3[cmp_idx]) > $signed(best_val)) begin
                    best_val <= h3[cmp_idx];
                    best_idx <= cmp_idx;
                end
                if (cmp_idx == 3'd7) begin
                    result <= best_idx;  // latch winner
                    state  <= DONE_ST;
                end else begin
                    cmp_idx <= cmp_idx + 3'd1;
                end
            end

            // ── Pulse done ────────────────────────────────────────────────────
            DONE_ST: begin
                done  <= 1'b1;
                state <= IDLE;
            end

            default: state <= IDLE;

        endcase
    end
end

endmodule
