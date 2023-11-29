
# commons-diff

Process changes to file pages on Wikimedia Commons since a specific date.
 
 Extracts changes that have been since the defined date to
 * a specific field in the information template
 * * SDC captions
 * * selected SDC statements.

For example output, see `example_output.json`

  

## USAGE PARAMETERS
* `--cutoff 2023-01-10`
	* Grab changes from the specific date
* `--list inputlist.txt`
* `--category "Name of category on Commons"`
Use either of these to specify which files to use.
If using `--list`, the list must consist of a list of files, eg
```
Damskor - Nordiska museet - Nordiska kompaniet NK K3c 1 0134.tif
Damskor - Nordiska museet - Nordiska kompaniet NK K3c 1 0130.tif
```
* `-- config configfile.json`
This file defines which changes to grab. It must be structured like
```
{
"info_template": {"Nordiska museet Bildminnen image" : "description"},
"relevant_sdc": ["P180"]
}
```

The three things we specify are
1) which infotemplate to process,
2) inside the infotemplate, which field to process (contains descriptions to diff),
3) which SDC statements to diff (P180 is depicts).
* `--out outputfile.json`
Optional, name of output file. If not used, a generic filename will be used.

See the file `out_examplelist.json` for an example of what the output looks like.

# process_changes_nordic_museum.py

This script converts the Json output from `commonsdiff.py` to a CSV file
adapted to the needs of the Nordic Museum in the project [100 000 Bildminnen](https://commons.wikimedia.org/wiki/Commons:Nordiska_museet/100_000_Bildminnen).

It breaks down the structured information into one row per piece of information added, making it easier to process filed with multiple categories or SDC statements added.

Each row starts with the inventory number and filename.

Usage:

`python3 process_changes_nordic_museum.py --source out_examplelist.json`

See the file `out_examplelist.csv` for an example of what is produced.

Some significant things that are done:

* Check for whether a Depicted object is a person (has instance of == human on Wikidata).
* Ignore categories starting with `100 000 Bildminnen`, they're internal organization categories in the project. Sometimes they can be added a longer time after the file upload but do not add valuable information.
* Only include wikitext description (in Swedish) if it has been edited.
* Only output SDC caption in Swedish.
* Add Swedish labels to depicted items.
* Add the the museum's inventory number extracted from the name of the file, taking advantage of the fact that files uploaded by WMSE follow a specific naming practice