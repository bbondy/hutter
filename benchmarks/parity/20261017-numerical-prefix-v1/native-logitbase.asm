
build/native-parity-v1/source/cmix:	file format mach-o arm64

Disassembly of section __TEXT,__text:

000000010004c2ac <__ZNK7Sigmoid9LogitBaseEf>:
10004c2ac: 528a1008    	mov	w8, #0x5080             ; =20608
10004c2b0: 72a8f868    	movk	w8, #0x47c3, lsl #16
10004c2b4: 1e270101    	fmov	s1, w8
10004c2b8: 1e210800    	fmul	s0, s0, s1
10004c2bc: 1e380008    	fcvtzs	w8, s0
10004c2c0: 5290d409    	mov	w9, #0x86a0             ; =34464
10004c2c4: 72a00029    	movk	w9, #0x1, lsl #16
10004c2c8: 6b09011f    	cmp	w8, w9
10004c2cc: 540000ad    	b.le	0x10004c2e0 <__ZNK7Sigmoid9LogitBaseEf+0x34>
10004c2d0: 529ff588    	mov	w8, #0xffac             ; =65452
10004c2d4: 72a7efe8    	movk	w8, #0x3f7f, lsl #16
10004c2d8: 1e270100    	fmov	s0, w8
10004c2dc: 1400000a    	b	0x10004c304 <__ZNK7Sigmoid9LogitBaseEf+0x58>
10004c2e0: 0aa87d08    	bic	w8, w8, w8, asr #31
10004c2e4: 1e230100    	ucvtf	s0, w8
10004c2e8: 5298a7c8    	mov	w8, #0xc53e             ; =50494
10004c2ec: 72a6e4e8    	movk	w8, #0x3727, lsl #16
10004c2f0: 1e270101    	fmov	s1, w8
10004c2f4: 5298a7c8    	mov	w8, #0xc53e             ; =50494
10004c2f8: 72a6d4e8    	movk	w8, #0x36a7, lsl #16
10004c2fc: 1e270102    	fmov	s2, w8
10004c300: 1f010800    	fmadd	s0, s0, s1, s2
10004c304: a9bf7bfd    	stp	x29, x30, [sp, #-0x10]!
10004c308: 910003fd    	mov	x29, sp
10004c30c: 1e2e1001    	fmov	s1, #1.00000000
10004c310: 1e203821    	fsub	s1, s1, s0
10004c314: 1e211800    	fdiv	s0, s0, s1
10004c318: 940004e4    	bl	0x10004d6a8 <_logf>
10004c31c: a8c17bfd    	ldp	x29, x30, [sp], #0x10
10004c320: d65f03c0    	ret
