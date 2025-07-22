# Json Cleaner

This small utility filter is intended to be used as the first filter in your Regolith Project. It will go through your packs, removing comments from your JSON files and allowing future filters to read the json safely without worrying about comments.

Additionally it can strip `$schema` fields, that are considered an error by Bedrock and minify JSON files.