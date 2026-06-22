#!/usr/bin/env python3
"""
DEPRECATED — do not use.

An earlier version of this skill prorated partial-month rent. That was WRONG:
Finance's validated settlement (dispute THE-17475) uses the FULL monthly rate for
every tenant (the "rental date" column is the billing date, not move-in; tenants are
mid-lease and bill a full month, even a mid-month break-lease).

Rent rule is now: full monthly rate, no proration. See SKILL.md.
This file is retained only to avoid breaking older references; it is not called.
"""
