"""Process changes to file pages on Wikimedia Commons since a specific date

Extracts changes that have been made since the defined date to:

* a specific field in the information template
* SDC captions
* selected SDC statements.

For example output, see example_output.json

If the file was uploaded after the defined date then the first edits by
the uploader are excluded (as e.g. SDC is added in a separate edit from the upload).

USAGE PARAMETERS

* --cutoff 2023-01-10

Grab changes from the specific date

* --list inputlist.txt
* --category "Name of category on Commons"

Use either of these to specify which files to use.
If using --list, the list must consist of a list of files, eg

Damskor - Nordiska museet - Nordiska kompaniet NK K3c 1 0134.tif
Damskor - Nordiska museet - Nordiska kompaniet NK K3c 1 0130.tif

* configfile.json looks like

{
    "info_template": {"Nordiska museet Bildminnen image" : "description"},
    "relevant_sdc": ["P180"]
}

So the three things we specify are 1) which infotemplate to process, 2) inside the
infotemplate, which field to process (contains descriptions to diff), 3) which SDC
statements to diff (P180 is depicts).

* --out outputfile.json

Optional, name of output file. If not used, a generic timestamped filename will
be used.

"""

import argparse
import datetime
import json
import re

import dateutil.parser as date_parser
import pywikibot
import mwparserfromhell


class Assistant(object):

    def get_label_from_wd_item(self, qid, language_code, fallback_language_code):
        site = pywikibot.Site("wikidata", "wikidata")
        repo = site.data_repository()
        item = pywikibot.ItemPage(repo, qid)
        item_dict = item.get()
        item_label = item_dict["labels"].get(language_code)
        if not item_label:
            item_label = item_dict["labels"].get(fallback_language_code)
    
    
    def array_to_string(self, array, delimiter):
        return delimiter.join(array)
    
    def package_results(self, results, cutoff, source, output_format):
        config_data = self.config.dump_self()
        timestamp = datetime.datetime.now().replace(microsecond=0).isoformat()
        if output_format == "json":
            packaged_results = {"config": config_data,
                    "results": results,
                    "meta":{"timestamp": timestamp,
                            "cutoff": cutoff,
                            "source": source,
                            "files": len(results)
                           }
                   }
        elif output_format == "csv":
            headers = ["changes_after", "filename", "file_uploaded", "baseline_revision",
                       "categories_removed", "categories_added", "description_old",
                       "description_current", "statements_added", "statements_removed"]
            header_row = ("\t").join(headers)
            result_rows = [header_row]
            for r in results:
                result_row = "\t".join([
                                       cutoff,
                                       r["filename"],
                                       r["uploaded"],
                                       r["baseline_revision"],
                                       self.array_to_string(r["categories"]["removed"], "|"),
                                       self.array_to_string(r["categories"]["added"], "|"),
                                       r["description"]["old"],
                                       r["description"]["new"],
                                       str(r["statements"]["added"]),
                                       str(r["statements"]["removed"]),
                                      ])
                result_rows.append(result_row)
            packaged_results = result_rows
        return packaged_results
    
    def results_to_file(self, data, filename, output_format):
        if output_format == "json":
            number_of_files = len(data)
            with open(filename, "w", encoding='utf8') as datafile:
                json.dump(data, datafile, ensure_ascii=False, sort_keys=True, indent=4)
        elif output_format == "csv":
            number_of_files = len(data) - 1
            with open(filename, 'w') as f:
                for line in data: 
                    f.write(f"{line}\n")
        print("Saved data of {} files to {}".format(number_of_files,
                                                    filename))

    
    def read_data_filelist(self, filename):
        datalist = []
        print("Loading files from list: {}".format(filename))
        with open(filename, 'r') as data:
            for line in data:
                datalist.append(line.strip())
        print("Loaded {} filenames.".format(len(datalist)))
        return datalist

    def read_data_category(self, categoryname):
        datalist = []
        print("Loading files from category: {}".format(categoryname))
        cat = pywikibot.Category(self.site, categoryname)
        for x in cat.articles(namespaces=-2):
            datalist.append(x.title())
        return datalist


    def create_pywikibot_timestamp(self, stringdate):
        return pywikibot.Timestamp.set_timestamp(date_parser.parse(stringdate))

    def __init__(self, config, site):
        self.config = config
        self.site = site

class Config(object):

    def load_json_file(self, filepath):
        # probably want to validate somehow
        with open(filepath) as json_file:
            return json.loads(json_file.read())

    def dump_self(self):
        return self.config


    def __init__(self, filepath):
        self.config = self.load_json_file(filepath)



class CommonsFile(object):


    def get_categories(self, page_text):
        categories = []
        regex_categories = r"\[\[Category\:(.*?)\]\]"
        all_categories = re.findall(regex_categories, page_text)
        for cat in all_categories:
            categories.append(cat.split("|")[0])
        return categories

    def create_commons_page(self, filename, site):
        if not filename.startswith("File:"):
            filename = "File:{}".format(filename)
        return pywikibot.FilePage(site, filename)


    def get_field_content(self, info_template, field_name, page_text):
        parsed_wikicode = mwparserfromhell.parse(page_text)
        templates = parsed_wikicode.filter_templates()
        for template in templates:
            if str(template.name).strip() == info_template:
                if [x for x in template.params if str(x.name).strip() == field_name]:
                    content = template.get(field_name).value.strip()
                    return content

    def get_revision_content(self, revision):
        # content loading needs to be forced (only fetches it if needed)
        revid = revision.revid
        _ = self.commons_page.getOldVersion(revid, force=True)
        return self.commons_page._revisions[revid]

    def get_baseline_revision(self):
        """
        Return the first revision after the cutoff date.

        If the file was uploaded after the cutoff date then this returns the first
        revision by another user than the uploader, or the last revision if no other
        users have interacted with the file.
        """
        baseline_date = self.assistant.create_pywikibot_timestamp(self.cutoff)
        all_revisions = list(self.commons_page.revisions())
        revs_before_cutoff = []
        for revision in all_revisions:
            if revision.timestamp < baseline_date:
                revs_before_cutoff.append(revision)
        if len(revs_before_cutoff) == 0:
            baseline_revision = self.get_first_rev_not_by_uploader(all_revisions)
        else:
            baseline_revision = revs_before_cutoff[0]
        return baseline_revision

    def get_first_rev_not_by_uploader(self, all_revisions):
        """
        Return the earliest revision by a user different from the uploader.

        If no such revision is found, return the last revision instead.
        """
        uploader = all_revisions[-1]["userid"]
        for rev in reversed(all_revisions[:-1]):
            if rev["userid"] != uploader:
                return rev
        # there are no revisions by other users, return the last revision
        return all_revisions[0]

    def process_descriptions(self):
        info_template = self.assistant.config.config.get("info_template")

        templ = list(info_template.keys())[0]
        field = info_template.get(templ)

        current_description = self.get_field_content(templ, field, self.current_page_content)
        baseline_description = self.get_field_content(templ, field, self.baseline_page_content)
        descriptions = {"old": baseline_description, "new": current_description, "changed": False}
        if baseline_description != current_description:
            descriptions["changed"] = True
        return descriptions

    def process_categories(self):
        current_categories = self.get_categories(self.current_page_content)
        baseline_categories = self.get_categories(self.baseline_page_content)
        added_categories = []
        removed_categories = []
        for cat in baseline_categories:
            if cat not in current_categories:
                removed_categories.append(cat)
        for cat in current_categories:
            if cat not in baseline_categories:
                added_categories.append(cat)
        return {"added":added_categories,
                "removed": removed_categories}

    def get_sdc(self):
        mid = 'M{}'.format(self.commons_page.pageid)
        request = self.site.simple_request(action='wbgetentities', ids=mid)
        data = request.submit()
        if data.get('entities').get(mid).get('pageid'):
            return data.get('entities').get(mid)
        return {}

    def process_captions(self):

        captions = []
        old_captions = []
        added_captions = []
        removed_captions = []
        labels = self.sdc.get("labels")
        if labels:
            for key in labels.keys():
                captions.append({key:labels.get(key).get('value')})

        old_mediainfo = self.baseline_revision.get("slots").get("mediainfo")
        if old_mediainfo:
            old_revision_content = self.get_revision_content(self.baseline_revision)
            old_sdc_content = json.loads(old_revision_content.get("slots").get("mediainfo").get("*"))
            old_sdc_labels = old_sdc_content.get("labels")
            if old_sdc_labels:
                for key in old_sdc_labels.keys():
                    old_captions.append({key:labels.get(key).get('value')})
        
        # now we compare old and new captions
        for captionpair in captions:
            if captionpair not in old_captions:
                added_captions.append(captionpair)
        for captionpair in old_captions:
            if captionpair not in captions:
                removed_captions.append(captionpair)

        return {"added": added_captions, "removed": removed_captions}

    def process_statements(self):
        current_statements = []
        old_statements = []
        added_statements = []
        removed_statements = []
        relevant_sdc = self.assistant.config.config.get("relevant_sdc")

        all_statements = self.sdc.get("statements")
        if all_statements:
            for x in all_statements:
                if x in relevant_sdc:
                    for y in all_statements.get(x):
                        statement_property = x
                        statement_value = y.get("mainsnak").get("datavalue").get("value").get("id")
                        current_statements.append((statement_property, statement_value))

        old_mediainfo = self.baseline_revision.get("slots").get("mediainfo")
        if old_mediainfo:
            old_revision_content = self.get_revision_content(self.baseline_revision)
            old_sdc_content = json.loads(old_revision_content.get("slots").get("mediainfo").get("*"))
            old_sdc_statements = old_sdc_content.get("statements")
            for x in old_sdc_statements:
                if x in relevant_sdc:
                    for y in old_sdc_statements.get(x):
                        old_statement_property = x
                        old_statement_value = y.get("mainsnak").get("datavalue").get("value").get("id")
                        old_statements.append((old_statement_property, old_statement_value))


        for stmnt in current_statements:
            if stmnt not in old_statements:
                added_statements.append(stmnt)
        for stmnt in old_statements:
            if stmnt not in current_statements:
                removed_statements.append(stmnt)

        return {"added": added_statements, "removed": removed_statements}

    def get_creation_date(self):
        return self.commons_page.oldest_revision.timestamp.isoformat()


    def process_history(self):
        self.baseline_revision = self.get_baseline_revision()
        self.baseline_page_content = self.commons_page.getOldVersion(self.baseline_revision.revid)
        self.current_page_content = self.commons_page.text
        self.sdc = self.get_sdc()
        self.file_history_data["baseline_revision"] = str(self.baseline_revision.revid)
        self.file_history_data["categories"] = self.process_categories()
        self.file_history_data["description"] = self.process_descriptions()
        self.file_history_data["captions"] = self.process_captions()
        self.file_history_data["statements"] = self.process_statements()
        self.file_history_data["uploaded"] = self.get_creation_date()


    def __init__(self, filename, assistant, cutoff, site):
        self.commons_page = self.create_commons_page(filename, site)
        self.site = site
        self.cutoff = cutoff
        self.assistant = assistant
        self.file_history_data = {"filename": filename,
                                  "categories": {},
                                  "description": {},
                                  "captions": [],
                                  "statements": [],
                                  "uploaded": ""}


def main(arguments):
    site = pywikibot.Site("commons", "commons")
    cutoff = arguments.get("cutoff")
    assistant = Assistant(Config(arguments.get("config")), site)

    history_dump = []

    if arguments.get("format"):
        if arguments.get("format").lower() in ["csv", "json"]:
            output_format = arguments.get("format").lower()
    else:
        output_format = "json"

    if arguments.get("out"):
        filename = arguments.get("out")
    else:
        filename = "out_{}.{}".format(datetime.datetime.now().replace(microsecond=0).isoformat(),
                                     output_format)
        
    
    
    if arguments.get("category"):
        source = "Category:{}".format(arguments.get("category"))
        files = assistant.read_data_category(arguments.get("category"))
    elif arguments.get("list"):
        source = arguments.get("list")
        files = assistant.read_data_filelist(arguments.get("list"))
    print("Output format: ", output_format)
    for fname in files:
        try:
            commons_file = CommonsFile(fname, assistant, cutoff, site)
            commons_file.process_history()
        except pywikibot.exceptions.NoPageError:
            continue
        history_dump.append(commons_file.file_history_data)
    
    results = assistant.package_results(history_dump, cutoff, source, output_format)
    
    assistant.results_to_file(results, filename, output_format)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    input_options = parser.add_mutually_exclusive_group(required=True)
    input_options.add_argument("--list")
    input_options.add_argument("--category")
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=False)
    parser.add_argument("--format")
    args = parser.parse_args()
    main(vars(args))
