def calc_new_seqno(old_seqno, data):
    return (old_seqno + len(data)) % (2 ** 16)

def calc_rcv_syn_fin_seqno(old_seqno):
    return (old_seqno + 1) % (2 ** 16)