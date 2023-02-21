
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
Optional, name of output file. If not used, a generic timestamped filename will be used.