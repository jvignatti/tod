#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
create_indicators.py

Create indicators at the level of census divisions.
"""

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import with_statement
import os
import pandas as pd

import pyredatam
from pyredatam import cpv2010arg
from path_finders import get_data_path, get_indicators_path

AREAS_LENIDS = {"PROV": 2, "DPTO": 5, "FRAC": 7, "RADIO": 9}


def get_or_create_indicators_df(area_level, df_example=None):
    df = get_indicators_df(area_level, AREAS_LENIDS[area_level])
    if df is not None:
        return df
    else:
        if not df_example:
            raise Exception("Can't create a df without an example with index.")
        df = pd.DataFrame(data={"Código": df_example.index})
        return replace_index(df, AREAS_LENIDS[area_level])


def get_indicators_df(area_level, id_len=7):
    path = get_indicators_path(area_level)

    if not os.path.isfile(path):
        return None
    else:
        df = pd.read_csv(path, encoding="utf-8")
        df = replace_index(df, id_len)
        return df


def get_data_from_query(area_level, query, redownload=False):
    path = get_data_path(area_level, "query", "censo", unicode(hash(query)))

    if not os.path.isfile(path) or redownload:
        html = pyredatam.cpv2010arg.make_query(query)

        df = pd.read_html(html, header=1, thousands=".")[0].dropna()
        if "Código" in df.columns:
            df = replace_index(df, AREAS_LENIDS[area_level])

        df.to_csv(path, encoding="utf-8")

    else:
        df = pd.read_csv(path, encoding="utf-8")
        if "Código" in df.columns:
            df = replace_index(df, AREAS_LENIDS[area_level])

    return df


def get_data(area_level, variable, universe_filter=None, redownload=False):
    path = get_data_path(area_level, variable, "censo", universe_filter)

    if not os.path.isfile(path) or redownload:
        query = pyredatam.arealist_query(area_level, variable,
                                         {"PROV": "02"},
                                         universe_filter=universe_filter)

        df = cpv2010arg.make_arealist_query(query)
        if "Código" in df.columns:
            df = replace_index(df, AREAS_LENIDS[area_level])

        df.to_csv(path, encoding="utf-8")

    else:
        df = pd.read_csv(path, encoding="utf-8")
        if "Código" in df.columns:
            df = replace_index(df, AREAS_LENIDS[area_level])

    return df


def replace_index(df, id_len=7):
    """Create GCBA shp ids and replace index with Census ids."""
    if "Unnamed: 0" in df.columns:
        df = df.drop("Unnamed: 0", 1)

    code_kw = df.columns[0]
    df[code_kw] = df[code_kw].astype(int)
    df[code_kw] = df[code_kw].astype(str)
    df[code_kw] = df[code_kw].str.zfill(id_len)

    def _strip_0(x):
        return x.lstrip("0")

    if id_len == 9 and "CO_FRAC_RA" not in df.columns:
        df["CO_FRAC_RA"] = df[code_kw].str[2:5].map(_strip_0) + \
            "_" + df[code_kw].str[5:7].map(_strip_0) + \
            "_" + \
            df[code_kw].str[7:9].map(_strip_0)

    elif id_len == 7 and "CO_FRACC" not in df.columns:
        df["CO_FRACC"] = df[code_kw].str[2:5] + \
            "_" + \
            df[code_kw].str[5:7].map(_strip_0)

    elif id_len == 5 and "COMUNAS" not in df.columns:
        df["COMUNAS"] = df[code_kw].str[-3:].map(_strip_0)

    return df.set_index(df[code_kw]).drop(code_kw, 1)


def main():
    pass

if __name__ == '__main__':
    main()