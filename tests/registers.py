# Primary Xemex V1.8 map, pp.21–22; independent expected payload paths.
EXTENDED = {
    0x8018: ('Q',), 0x801A: ('S',), 0x801C: ('PF',),
    0x8024: ('l1','Q'), 0x8026: ('l2','Q'), 0x8028: ('l3','Q'),
    0x802A: ('l1','S'), 0x802C: ('l2','S'), 0x802E: ('l3','S'),
    0x8100: ('E_IMPORT',), 0x8106: ('E_EXPORT',),
    0x8C00: ('Q+',), 0x8C02: ('Q-',),
    0x8C04: ('l1','Q+'), 0x8C06: ('l1','Q-'),
    0x8C08: ('l2','Q+'), 0x8C0A: ('l2','Q-'),
    0x8C0C: ('l3','Q+'), 0x8C0E: ('l3','Q-'),
    0x8C10: ('EQ1',), 0x8C12: ('EQ2',), 0x8C14: ('EQ3',), 0x8C16: ('EQ4',),
    0x8C18: ('l1','VSAGS'), 0x8C1A: ('l2','VSAGS'), 0x8C1C: ('l3','VSAGS'),
    0x8C1E: ('l1','VSWELLS'), 0x8C20: ('l2','VSWELLS'), 0x8C22: ('l3','VSWELLS'),
    0x8C24: ('PFAIL',), 0x8C26: ('LPFAIL',),
    0x8C28: ('P+',), 0x8C2A: ('P-',),
    0x8C2C: ('l1','P+'), 0x8C2E: ('l1','P-'),
    0x8C30: ('l2','P+'), 0x8C32: ('l2','P-'),
    0x8C34: ('l3','P+'), 0x8C36: ('l3','P-'),
}
