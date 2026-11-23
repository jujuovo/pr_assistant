"""Award stages derived from catalog classification and policy page 6 clause (6)."""


def competition_award_levels(item):
    """National contests may recognize provincial-stage awards of the same category.

    CSP and ICPC/CCPC retain their explicit percentile/format-specific policies.
    The immutable catalog's original competition classification is not modified.
    """
    levels = list(item['levels'])
    if ('national' in levels and 'provincial' not in levels
            and item['event_family'] not in {'csp', 'icpc', 'ccpc'}):
        levels.append('provincial')
    return levels
