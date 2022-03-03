import os, re, strutils, json
 
for file in walkDirRec os.getCurrentDir():
    var newF: string
    var newL: string
    if file.match re".*\.json":
        for line in file.readFile().splitLines():
            newL = line
            if line.contains("//"):
                newL = line.replace("//" & line.split("//")[1], "")
            newF = newF & newL & "\n"
        file.writeFile(newF.parseJson().pretty())
        echo "formatted " & file.splitFile().name & ".json"
    if file.match re".*\.lang":
        for line in file.readFile().splitLines():
            newL = line
            if line.startsWith("##") == false and line != "":
                newF = newF & newL & "\n"
        file.writeFile(newF)
        echo "formatted " & file.splitFile().name & ".lang"
    if file.match re".*\.mcfunction":
        for line in file.readFile().splitLines():
            newL = line
            if line.startsWith("#") == false and line != "":
                newF = newF & newL & "\n"
        file.writeFile(newF)
        echo "formatted " & file.splitFile().name & ".mcfunction"