#
# This file is part of pleiades_wikidata
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2024 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#
"""
Compare Pleiades citations of Wikidata and vice versa
"""

from airtight.cli import configure_commandline
from copy import deepcopy
from csv import DictWriter
from datetime import datetime
from encoded_csv import get_csv
import json
import logging
from pathlib import Path
from pprint import pprint

logger = logging.getLogger(__name__)

DEFAULT_LOG_LEVEL = logging.WARNING
DEFAULT_INDEX_PATH = str(
    Path("~/Documents/files/P/pleiades.datasets/data/indexes/wikidata.json")
    .expanduser()
    .resolve()
)
DEFAULT_WIKIDATA_PATH = str(Path("./data/wd2all.tsv").resolve())
DEFAULT_OUTPUT_DIRECTORY = str(Path("./data/").resolve())

OPTIONAL_ARGUMENTS = [
    [
        "-l",
        "--loglevel",
        "NOTSET",
        "desired logging level ("
        + "case-insensitive string: DEBUG, INFO, WARNING, or ERROR",
        False,
    ],
    ["-v", "--verbose", False, "verbose output (logging level == INFO)", False],
    [
        "-w",
        "--veryverbose",
        False,
        "very verbose output (logging level == DEBUG)",
        False,
    ],
    ["-d", "--data", DEFAULT_WIKIDATA_PATH, "path to the Wikidata CSV file", False],
    [
        "-i",
        "--index",
        DEFAULT_INDEX_PATH,
        "path to the Pleiades->Wikidata index JSON file",
        False,
    ],
    [
        "-o",
        "--output_directory",
        DEFAULT_OUTPUT_DIRECTORY,
        "path to the output directory",
        False,
    ],
    [
        "-x",
        "--date",
        datetime.now().isoformat().split("T")[0],
        "date of the update",
        False,
    ],
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
]


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)

    # determine which pleiades places have references pointing at wikidata
    index_path = Path(kwargs["index"]).expanduser().resolve()
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    del f
    logger.info(f"Loaded index from {index_path} ({len(index)} entries)")
    p2w = dict()
    puris = [
        k for k in index.keys() if k.startswith("https://pleiades.stoa.org/places/")
    ]
    p2w = dict()
    for puri in puris:
        values = [
            v
            for v in index[puri]["alignments"]
            if v.startswith("https://www.wikidata.org/wiki/")
        ]
        if values:
            p2w[puri] = values[0]

    # determine which wikidata items point at pleiades places and note which are bidirectional
    data_path = Path(kwargs["data"]).expanduser().resolve()
    wikidata = get_csv(data_path, dialect="excel-tab")
    logger.info(
        f"Loaded Wikidata from {data_path} ({len(wikidata['content'])} entries)"
    )
    logger.debug(f"wikidata fieldnames: {wikidata['fieldnames']}")
    wikidata_dict = dict()
    wikidata_dict_index = dict()
    w2p = dict()
    bidirectional = set()
    cited_puris = set()  # puris that have already been cited in a wikidata item
    multicited_puris = set()
    for row in wikidata["content"]:
        wuri = row["item"]
        wikidata_dict[wuri] = row
        puri = f"https://pleiades.stoa.org/places/{row['pleiades']}"
        if puri in cited_puris:
            multicited_puris.add(puri)
        else:
            cited_puris.add(puri)
        try:
            w2p[wuri]
        except KeyError:
            w2p[wuri] = set()
        w2p[wuri].add(puri)
        wikidata_dict_index[puri] = wuri
        try:
            p2w[puri]
        except KeyError:
            pass
        else:
            bidirectional.add(puri)

    # determine and report on what we've found
    logger.info(f"Found {len(bidirectional)} bidirectional links")
    only_pleiades = set(p2w.keys()) - bidirectional
    logger.info(
        f"Found {len(only_pleiades)} additional links from Pleiades to Wikidata (out of {len(p2w)})"
    )
    only_wikidata = {v for subset in w2p.values() for v in subset} - bidirectional
    logger.info(
        f"Found {len(only_wikidata)} additional links from Wikidata to Pleiades (out of {len(w2p)})"
    )
    multiple_p4w = {
        this_wuri for this_wuri, these_puris in w2p.items() if len(these_puris) > 1
    }
    logger.info(
        f"Found {len(multiple_p4w)} wikidata items that incorrectly link to more than one Pleiades place."
    )
    multicited = dict()
    for this_puri in multicited_puris:
        multicited[this_puri] = {
            this_wuri
            for this_wuri, these_puris in w2p.items()
            if this_puri in these_puris
        }
    logger.info(
        f"Found {len(multicited)} Pleiades places that are each linked (incorrectly) by more than one Wikidata item."
    )

    output_path = Path(kwargs["output_directory"]).expanduser().resolve()

    output_path.mkdir(parents=True, exist_ok=True)
    p2w_path = output_path / "pleiades_not_in_wikidata.csv"
    with open(p2w_path, "w", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=["pleiades_uri", "wikidata_uri"])
        writer.writeheader()
        for puri in only_pleiades:
            writer.writerow({"pleiades_uri": puri, "wikidata_uri": p2w[puri]})
    logger.info(f"Wrote {len(only_pleiades)} Pleiades->Wikidata links to {p2w_path}")

    w2p_path = output_path / "wikidata_not_in_pleiades.csv"
    with open(w2p_path, "w", encoding="utf-8") as f:
        writer = DictWriter(
            f,
            fieldnames=[
                "pleiades_uri",
                "wikidata_uri",
                "wikidata_label",
                "wikidata_description",
                "wikidata_coordinates",
                "chronique_id",
                "dare_id",
                "geonames_id",
                "gettytgn_id",
                "idaigaz_id",
                "loc_id",
                "manto_id",
                "nomisma_id",
                "topostext_id",
                "trismegistos_id",
                "viaf_id",
                "vici_id",
                "wikipedia_en",
            ],
        )
        writer.writeheader()
        for puri in only_wikidata:
            logger.debug(puri)
            d = dict()
            for k, v in wikidata_dict[wikidata_dict_index[puri]].items():
                logger.debug(f"k: '{k}'")
                logger.debug(f"v: '{v}'")
                if k == "item":
                    d["wikidata_uri"] = v
                elif k == "pleiades":
                    d["pleiades_uri"] = puri
                elif k == "itemLabel":
                    d["wikidata_label"] = v
                elif k == "itemDescription":
                    d["wikidata_description"] = v
                elif k == "coordinates":
                    d["wikidata_coordinates"] = v
                elif k.endswith("s"):
                    d[k[:-1]] = v
                else:
                    d[k] = v
            writer.writerow(d)
    logger.info(f"Wrote {len(only_wikidata)} Wikidata->Pleiades links to {w2p_path}")

    multiple_p4w_path = output_path / "wikidata_that_cite_multiple_pleiades.csv"
    with open(multiple_p4w_path, "w", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=["wikidata_uri"])
        writer.writeheader()
        for wuri in multiple_p4w:
            writer.writerow({"wikidata_uri": wuri})
    del f

    multicited_p_path = output_path / "pleiades_cited_by_multiple_wikidata.json"
    with open(multicited_p_path, "w", encoding="utf-8") as f:
        json.dump(multicited, f, cls=SetEncoder)
    del f

    base_url = "https://github.com/isawnyu/pleiades_wikidata/blob/main/data/"
    msg = [
        f"Pleiades <-> Wikidata and other gazetteer alignments updated {kwargs['date']}:\n",
        f"{len(wikidata['content'])} Wikidata entities include a Pleiades ID property and ",
        f"{len(p2w)} Pleiades entities include a Wikidata ID property. ",
        f"Of these, {len(bidirectional)} are mutual (bidirectional).\n\n",
        f"{len(only_wikidata)} Pleiades resources to which Wikidata links can be added after they are checked: ",
        f"{base_url}wikidata_not_in_pleiades.csv\n\n",
        f"{len(only_pleiades)} Wikidata items to which Pleiades IDs can be added after they are checked: ",
        f"{base_url}pleiades_not_in_wikidata.csv\n\n",
        f"{len(multiple_p4w)} Wikidata items that each link to more than one Pleiades ID (violates the ",
        f"Wikidata 'single-value constraint'): {base_url}wikidata_that_cite_multiple_pleiades.csv\n\n",
        f"{len(multicited)} Pleiades resources to each of which more than one Wikidata Item link (violates ",
        f"the Wikidata 'distinct-values constraint'): {base_url}pleiades_cited_by_multiple_wikidata.json",
    ]
    msg = "".join(msg)
    print(msg)


if __name__ == "__main__":
    main(
        **configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL
        )
    )
