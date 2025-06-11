const glob = require("glob");
const fs = require("fs");
const JSON5 = require("json5");
const Hjson = require("hjson");

const defSettings = {
  include: ["**/*.json5", "**/*.hjson", "**/*.json"],
  pretty: true,
  extension_map: {
    "json5": "json",
    "hjson": "json"
  }
};

const argParsed = process.argv[2] ? JSON.parse(process.argv[2]) : {};
const settings = Object.assign({}, defSettings, argParsed);

for (const pattern of settings.include) {
  glob(pattern, null, function (er, files) {
    files.forEach(function (file) {
      fs.readFile(file, "utf8", function (err, data) {
        let resultName = file.substr(0, file.lastIndexOf(".")) + "." + (settings.extension_map[file.substr(file.lastIndexOf(".") + 1)] || file.substr(file.lastIndexOf(".") + 1));
        console.log("Converting " + file + " into " + resultName);
        let output = null;
        try {
          output = Hjson.parse(data);
        } catch(e) {
          try {
            output = JSON5.parse(data);
          } catch(e) {
            console.error("Failed to parse " + file);
            console.error(e);
            process.exit(1);
            return;
          }
        }
        fs.unlinkSync(file);
        fs.writeFileSync(
          resultName,
          JSON.stringify(output, null, settings.pretty ? 4 : 0)
        );
      });
    });
  });
}