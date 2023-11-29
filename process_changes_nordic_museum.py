import argparse
import json
import csv
import pywikibot


"""
USAGE

python3 process_changes_nordic_museum.py --source out_examplelist.json

Converts output made by commonsdiff.py to a one file per line
CSV format.

The input file has to bee a JSON file made by commonsdiff.py

"""""


WIKIDATA_CACHE = {}


def get_label_from_wd_item(qid, language_code, fallback_language_code):
    site = pywikibot.Site("wikidata", "wikidata")
    repo = site.data_repository()
    if WIKIDATA_CACHE.get(qid):
        item_label = WIKIDATA_CACHE.get(qid)
    else:
        item = pywikibot.ItemPage(repo, qid)
        item_dict = item.get()
        item_label = item_dict["labels"].get(language_code)
        if not item_label:
            item_label = item_dict["labels"].get(
                fallback_language_code)  # what if none in either?
        WIKIDATA_CACHE[qid] = item_label
    return item_label


def read_sourcefile(filepath):
    '''Read source data'''
    with open(filepath) as f:
        sourcecontent = json.load(f)
    return sourcecontent


def check_jsoncontent_is_reasonable(sourcecontent):
    '''Check if the expected content is in source file.'''
    required_keys = ['meta', 'results', 'config']
    return set(required_keys).issubset(set(sourcecontent.keys()))


def get_inventory_number_from_filename(filename):
    """
    For files with filenames like:
    Svenska Renault AB. Bilar i natur - Nordiska museet - NMAx.0030805.tif

    Retrieve the Nordiska inventory number from filename.
    """
    invno = "???"
    good_start = "NM"
    filename_parts = filename.split("-")
    if filename_parts[-1].strip().startswith(good_start):
        invno = filename_parts[-1].strip().rsplit('.', 1)[0]
    return invno


def clean_description(content):
    """Remove lang template if present"""
    if content.startswith("{{") and "|" in content:
        content = content.split("|")[-1].replace("}", "").replace("{", "")
    return content


def convert_to_nordic_museum(content, target_filename):
    """
    Convert json produced by commonsdiff.py to a csv prefered by
    Nordic Museum.

    Since a file can have several categories/depicts added,
    if that's the case, the file gets multiple rows
    with the same file name and one new cat/depicts.
    """
    meat_content = content.get("results")
    print("Files found: {}".format(len(meat_content)))
    with open(target_filename, 'w', newline='') as outputfile:
        writer = csv.writer(outputfile)
        header = ["invno", "filename", "added_category",
                  "added_depicts_q", "added_depicts_label",
                  "added_caption_sv", "updated_description_sv"]
        writer.writerow(header)
    for x in meat_content:
        filename = x.get("filename")
        print("Processing {}.".format(filename))
        nordic_id = get_inventory_number_from_filename(filename)
        added_sdc = x.get("statements").get("added")
        added_categories = x.get("categories").get("added")
        added_captions = x.get("captions").get("added")
        description = x.get("description")
        updated_description = None
        if description.get("changed"):
            updated_description = clean_description(description.get("new"))
        for added_category in added_categories:
            if not added_category.startswith("100 000 Bildminnen"):
                # exclude project categories, not interesting
                with open(target_filename, 'a', newline='') as outputfile:
                    writer = csv.writer(outputfile)
                    writer.writerow(
                        [nordic_id, filename, added_category, "", "", "", ""])
        for sdc in added_sdc:
            if sdc[0] == "P180":
                depicts_value = sdc[1]
                depicts_label = get_label_from_wd_item(
                    depicts_value, "sv", "en")
                with open(target_filename, 'a', newline='') as outputfile:
                    writer = csv.writer(outputfile)
                    writer.writerow(
                        [nordic_id, filename, "",
                         depicts_value, depicts_label, "", "", ""])
        for caption in added_captions:
            caption_meat = caption.get("sv")
            with open(target_filename, 'a', newline='') as outputfile:
                writer = csv.writer(outputfile)
                writer.writerow(
                    [nordic_id, filename, "", "", "", caption_meat, ""])
        if updated_description:
            with open(target_filename, 'a', newline='') as outputfile:
                writer = csv.writer(outputfile)
                writer.writerow(
                    [nordic_id, filename, "", "", "", "", updated_description])
    print("Saved {}.".format(target_filename))


def main(arguments):
    sourcefile = arguments.get("source")
    sourcecontent = read_sourcefile(sourcefile)
    target_filename = "{}.{}".format(sourcefile.split(".")[0], "csv")
    if not check_jsoncontent_is_reasonable(sourcecontent):
        print("Something seems to be wrong with source file {}.".
              format(sourcefile))
    else:
        print("Loaded file {}.".format(sourcefile))
        convert_to_nordic_museum(sourcecontent, target_filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    main(vars(args))
