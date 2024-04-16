def calc_new_seqno(old_seqno, data):
    return (old_seqno + len(data)) % (2 ** 16)
