.text
.globl main
main:
    li   s0, 0xF0000000     # LED Matrix base

    
    li   s1, 0x00FF0000     # FULL RED
    li   s2, 0x00FFFF00     # FULL YELLOW
    li   s3, 0x0000FF00     # FULL GREEN


    li   s4, 0x00330000     # DIM RED
    li   s5, 0x00333300     # DIM YELLOW
    li   s6, 0x00003300     # DIM GREEN

  
traffic_loop:
    # Phase 1: Post1=GREEN, Post2=RED
    sw   s4,  0(s0)         # Post1 Red    - dim
    sw   s1,  4(s0)         # Post2 Red    - FULL
    sw   s5,  8(s0)         # Post1 Yellow - dim
    sw   s5, 12(s0)         # Post2 Yellow - dim
    sw   s3, 16(s0)         # Post1 Green  - FULL
    sw   s6, 20(s0)         # Post2 Green  - dim
    jal  ra, debug_delay

    # Phase 2: Post1=YELLOW, Post2=RED
    sw   s4,  0(s0)         # Post1 Red    - dim
    sw   s1,  4(s0)         # Post2 Red    - FULL
    sw   s2,  8(s0)         # Post1 Yellow - FULL
    sw   s5, 12(s0)         # Post2 Yellow - dim
    sw   s6, 16(s0)         # Post1 Green  - dim
    sw   s6, 20(s0)         # Post2 Green  - dim
    jal  ra, debug_delay

    # Phase 3: Post1=RED, Post2=GREEN
    sw   s1,  0(s0)         # Post1 Red    - FULL
    sw   s4,  4(s0)         # Post2 Red    - dim
    sw   s5,  8(s0)         # Post1 Yellow - dim
    sw   s5, 12(s0)         # Post2 Yellow - dim
    sw   s6, 16(s0)         # Post1 Green  - dim
    sw   s3, 20(s0)         # Post2 Green  - FULL
    jal  ra, debug_delay

    # Phase 4: Post1=RED, Post2=YELLOW
    sw   s1,  0(s0)         # Post1 Red    - FULL
    sw   s4,  4(s0)         # Post2 Red    - dim
    sw   s5,  8(s0)         # Post1 Yellow - dim
    sw   s2, 12(s0)         # Post2 Yellow - FULL
    sw   s6, 16(s0)         # Post1 Green  - dim
    sw   s6, 20(s0)         # Post2 Green  - dim
    jal  ra, debug_delay

    j    traffic_loop

debug_delay:
    li   t4, 5
delay_loop:
    addi t4, t4, -1
    bnez t4, delay_loop
    ret