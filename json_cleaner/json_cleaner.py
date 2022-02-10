import glob
import json

def get_json_from_file(fh):

    try:
        # If possible, read the file as JSON
        return json.loads(fh)
    except:
        # If not, read the file as a string, and try to parse it as JSON
        contents = ""
        for line in fh.splitlines():
            cleanedLine = line.split("//", 1)[0]
            if len(cleanedLine) > 0 and line.endswith("\n") and "\n" not in cleanedLine:
                cleanedLine += "\n"
            contents += cleanedLine
        while "/*" in contents:
            preComment, postComment = contents.split("/*", 1)
            contents = preComment + postComment.split("*/", 1)[1]
        return json.loads(contents)

def main():
    folders = ('BP', 'RP')
    for folder in folders:
        for file in glob.glob(folder + "/**/*.json", recursive=True):
            with open(file, "r") as fh:
                json_data = get_json_from_file(fh.read())
            
            with open(file, "w") as fh:
                json.dump(json_data, fh, indent=2)

main()