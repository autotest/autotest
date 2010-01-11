import re,string


class reason_counter:
    def __init__(self, wording):
        self.wording = wording
        self.num = 1

    def update(self, new_wording):
        self.num += 1
        self.wording = new_wording

    def html(self):
        if self.num == 1:
            return self.wording
        else:
            return "%s (%d+)" % (self.wording, self.num)


def numbers_are_irrelevant(txt):
    ## ? when do we replace numbers with NN ?
    ## By default is always, but
    ## if/when some categories of reasons choose to keep their numbers,
    ## then the function shall return False for such categories
    return True


def aggregate_reason_fields(reasons_list):
    # each reason in the list may be a combination
    # of | - separated reasons.
    # expand into list
    reasons_txt = '|'.join(reasons_list)
    reasons = reasons_txt.split('|')
    reason_htable = {}
    for reason in reasons:
        reason_reduced = reason.strip()
        ## reduce whitespaces
        reason_reduced = re.sub(r"\s+"," ", reason_reduced)

        if reason_reduced == '':
            continue # ignore empty reasons

        if numbers_are_irrelevant(reason_reduced):
            # reduce numbers included into reason descriptor
            # by replacing them with generic NN
            reason_reduced = re.sub(r"\d+","NN", reason_reduced)

        if not reason_reduced in reason_htable:
            reason_htable[reason_reduced] = reason_counter(reason)
        else:
            ## reason_counter keeps original ( non reduced )
            ## reason if it occured once
            ## if reason occured more then once, reason_counter
            ## will keep it in reduced/generalized form
            reason_htable[reason_reduced].update(reason_reduced)

    generic_reasons = reason_htable.keys()
    generic_reasons.sort(key = (lambda k: reason_htable[k].num),
                         reverse = True)
    return map(lambda generic_reason: reason_htable[generic_reason].html(),
                            generic_reasons)
