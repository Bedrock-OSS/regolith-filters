# Json Cleaner

This small utility filter is intended to be used as the first filter in your Regolith project. It goes through your packs, removing comments from your JSON files and allowing later filters to read the JSON safely without worrying about comments.

Additionally it can strip root-level `$schema` fields, which Bedrock considers an error, and minify JSON files.
