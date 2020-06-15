# ! /usr/bin/python3
'''
Usage        : mmu_gen.py [-32|-64]
-h           : this help
-32          : aarch32 short table & ARM assembly, default
-64          : aarch64 short table & GNU assembly

This script generates ARMv8 short format MMU tables

Example:
$ mmu_gen,py -32
'''

import sys, getopt, os, shutil
import time, logging

def usage():
    ''' Display command usage.'''
    sys.stderr.write(__doc__)
    sys.stderr.flush()

global ttb_tbl, slttb_tbl
global TTB, SLTTB

def init_tbl():
    global arch, asm_op, comment
    global ttb_tbl, slttb_tbl, slttb_ptr, slttb_inc, slttb_idx, slttb_idx_inc
    global pg4k_wbwas, pg4k_dvs, pg4k_sos
    global sec_wbwas, sec_dvs, sec_sos
    global supsec_wbwas, supsec_dvs, supsec_sos
    global zlist, line_idx, line_tag

    ttb_tbl = []
    slttb_tbl = []
    slttb_idx = 0
    zlist = []
    line_idx = 0
    line_tag = ''
    if arch == 32:
        asm_op = 'DCD'
        comment = ';#'
        slttb_inc = 0x400
        slttb_idx_inc = 256
        # Level 2 - 4K page attribute
        pg4k_wbwas   = 0x0000004E             # WB-WA-S
        pg4k_dvs     = 0x00000406             # DV-S
        pg4k_sos     = 0x00000402             # SO-S
        # Level 1 - 1M section attribute
        sec_wbwas    = 0x0001100E             # WB-WA-S
        sec_dvs      = 0x00010006             # DV-S
        sec_sos      = 0x00010002             # SO-S
        # Level 1 - 16M supersection attribute
        supsec_wbwas = 0x0005100E             # WB-WA-S
        supsec_dvs   = 0x00050006             # DV-S
        supsec_sos   = 0x00050002             # SO-S
    elif arch == 64:
        asm_op = 'dcd'
        comment = '//'

def trans_entry(addr, tag):
    global ttb_tbl, slttb_ptr, slttb_offset, slttb_idx, slttb_idx_offset
    index = (addr >> 20) & 0xfff
    val = slttb_ptr + 1
    ttb_tbl.append([index, val, tag, addr])
    slttb_ptr += slttb_inc
    slttb_idx += slttb_idx_inc

def pg4k_entry(addr, num, attr, tag ):
    global slttb_tbl, slttb_idx, slttb_idx_inc
    n_addr = addr
    for i in range(0, num):
        idx = (n_addr >> 12) & 0xff
        val = (idx << 24) | attr
        slttb_tbl.append([idx, val, tag, n_addr])
        n_addr += 4096

def sec_entry(addr, num, attr, tag ):
    global ttb_tbl
    n_addr = addr
    for i in range(0, num):
        idx = (n_addr >> 20) & 0xfff
        val = (n_addr & 0xfff00000) | attr
        ttb_tbl.append([idx, val, tag, n_addr])
        n_addr += (1024 * 1024)

def supsec_entry(addr, num, attr, tag ):
    global ttb_tbl
    n_addr = addr
    for i in range(0, num):
        index = (n_addr >> 20) & 0xfff
        val = (n_addr & 0xff000000) | attr
        for j in range(0, 16):
            ttb_tbl.append([index + j, val, tag, n_addr])
        n_addr += 0x01000000

# FIXME - modify this function as needed
def define_32_tbl():
    global TTB, SLTTB, slttb_ptr
    TTB = 0x4000
    SLTTB = 0x8000
    slttb_ptr = SLTTB
    # First 1 MB
    trans_entry(0x00000000, "1st MB @ 2nd level table")
    pg4k_entry(0x00000000, 80, pg4k_wbwas, "SRAM_P0_L")
    pg4k_entry(0x00080000, 1, pg4k_sos, "Trickbox")
    pg4k_entry(0x00090000, 1, pg4k_wbwas, "WFDROM")
    pg4k_entry(0x000A0000, 1, pg4k_wbwas, "BURINROM")
    pg4k_entry(0x000B0000, 1, pg4k_wbwas, "")
    pg4k_entry(0x000C0000, 3, pg4k_wbwas, "(old) EXT AHB")
    pg4k_entry(0x000F0000, 1, pg4k_sos, "GPIO1 & GPIO2")
    pg4k_entry(0x000F1000, 1, pg4k_sos, "I2C")
    pg4k_entry(0x000F2000, 1, pg4k_sos, "IEC")
    pg4k_entry(0x000F4000, 1, pg4k_sos, "RTC")                  # ??
    # 2nd 1 MB
    trans_entry(0x00100000, "2nd MB @ 2nd level table")
    pg4k_entry(0x00100000, 1, pg4k_sos, "DMA_L0_CTRL")
    pg4k_entry(0x00101000, 1, pg4k_sos, "DMA_L1_CTRL")
    pg4k_entry(0x00102000, 1, pg4k_sos, "TG_L0_CTRL")
    pg4k_entry(0x00103000, 1, pg4k_sos, "TM_L0_CTRL")
    pg4k_entry(0x00104000, 1, pg4k_sos, "SRAM_L0_CTRL")
    pg4k_entry(0x00105000, 1, pg4k_sos, "SRAM_L1_CTRL")
    # 3rd 1 MB
    sec_entry(0x00300000, 1, sec_wbwas, "SRAM_P0_H (512KB)")
    # CMNCFG
    sec_entry(0x04000000, 64, sec_sos, "CMNCFG")
    sec_entry(0x08000000, 8, sec_wbwas, "OCM (8 MB)")
    sec_entry(0x0C000000, 1, sec_wbwas, "SRAM_L0 (128KB)")
    sec_entry(0x10000000, 1, sec_wbwas, "SRAM_L1 (128KB)")
    sec_entry(0x14000000, 1, sec_wbwas, "TM_L0 (4KB)")
    # SRAM Cubes
    supsec_entry(0x20000000, 16, supsec_wbwas, "SRAM_M0 Cube (256 MB)")
    supsec_entry(0x30000000, 16, supsec_wbwas, "SRAM_M1 Cube (256 MB)")
    supsec_entry(0x40000000, 16, supsec_wbwas, "SRAM_M2 Cube (256 MB)")
    supsec_entry(0x50000000, 16, supsec_wbwas, "SRAM_M3 Cube (256 MB)")
    return

def define_64_tbl():
    return

def define_tbl():
    global arch
    if arch == 32:
        define_32_tbl()
    else:
        define_64_tbl()

def print_list(list, idx, tag, addr):
    global comment
    line = "        " + asm_op + "     "
    for i in range(0, len(list)):
        if list[i] == 0:
            line += str(list[i])
        else:
            line += '0x' + format(list[i], '08X')
        if i != len(list) - 1:
            line += ', '
    cmt = 0
    cmtline = ''
    if idx != -1:
        cmt = 1
        cmtline += format(idx, '04X') + ' '
    if addr != -1:
        cmt = 1
        cmtline += '0x' + format(addr, '08X') + ' '
    if tag != '':
        cmt = 1
        cmtline += tag
    if cmt == 1:
        print(line.ljust(65, ' ') + comment, cmtline)
    else:
        print(line)

def gen_entry(list):
    global zlist, line_idx, line_tag, line_addr

    if len(zlist) > 0:
        if line_tag != list[2]:
            print_list(zlist, line_idx, line_tag, line_addr)
            zlist = [list[1]]
            line_idx = list[0]
            line_tag = list[2]
            line_addr = list[3]
        else:
            if list[0] % 4 == 0:
                print_list(zlist, line_idx, line_tag, line_addr)
                zlist = [list[1]]
                line_idx = list[0]
                line_tag = list[2]
                line_addr = list[3]
            else:
                zlist.append(list[1])
    else:
        zlist = [list[1]]
        line_idx = list[0]
        line_tag = list[2]
        line_addr = list[3]

def gen_zero(idx):
    global zlist, line_idx, line_tag, line_addr

    if len(zlist) > 0:
        if zlist[0] != 0:
            print_list(zlist, line_idx, line_tag, line_addr)
            zlist = []
            line_idx = -1
            line_tag = ''
            line_addr = -1
            if idx % 16 == 0:
                line_idx = idx
            zlist.append(0)
        else:
            if idx % 16 == 0:
                print_list(zlist, line_idx, line_tag, line_addr)
                zlist = []
                line_idx = idx
                line_tag = ''
                line_addr = -1
            zlist.append(0)
    else:
        if idx % 16 == 0:
            line_idx = idx
            line_tag = ''
            line_addr = -1
        zlist.append(0)

def print_tbl(tbl):
    global zlist, line_idx, line_tag, line_addr
    idx = 0
    limit = len(tbl)
    for i in range(0, 4096):
        if idx < limit:
            rec = tbl[idx]
            if i != rec[0]:
                gen_zero(i)
            else:
                gen_entry(rec)
                idx += 1
        else:
            gen_zero(i)
    print_list(zlist, line_idx, line_tag, line_addr)

def gen_tbl():
    global ttb_tbl, slttb_tbl
    print(";# These tables are generated with mmu_gen.py.  JH 2020.06")
    print(";# Level 1 table")
    print("TTB")
    print_tbl(ttb_tbl)
    print(";# Level 2 table")
    print("SLTTB")
    print_tbl(slttb_tbl)

def main(argv):
    global arch
    arch = 32
    # getopt
    try:
        opts, args = getopt.getopt(argv, "h")
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    # handle options
    for opt, optarg in opts:
        if opt == '-h':
            usage()
            sys.exit()
        elif opt == '-32':
            arch = 32
        elif opt == '-64':
            arch = 64
        else:
            usage()
            sys.exit()
    if len(args) != 0:
        usage()
        sys.exit()
    # init_tbl
    init_tbl()
    define_tbl()
    gen_tbl()

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))